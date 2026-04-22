"""角色卡生成用例模块，负责请求准备、分析整合与结果编排。"""

from dataclasses import dataclass, field
from typing import Any

from ..checkpoint import load_resumable_checkpoint
from .app_container import TaskRuntimeDependencies
from .character_card_context import load_character_analyses, compress_character_analyses
from .character_card_output import (
    CharacterCardOutputPaths,
    finalize_character_card_success,
    prepare_output_paths,
)
from .task_prepared import PreparedGenerateCharacterCardTask
from .task_state import CharacterCardResumeState, build_initial_state_factory, build_resume_state_loader
from .task_result_factory import ok_task_result, fail_task_result, build_dataclass_result_mapper
from .task_prepare_context import (
    build_on_resumed_logger,
    build_clean_payload_loader,
    build_prepared_state_builder,
    prepare_task_context,
)
from ..config.request_config import build_llm_config
from ..llm.character_card_flow import generate_character_card
from ..llm.shared import LANG_NAMES, format_vndb_section
from ..domain import GenerateCharacterCardRequest, fail_result, TASK_TYPE_GENERATE_CHARA_CARD


@dataclass(frozen=True)
class CharacterCardTaskResult:
    success: bool
    message: str = ""
    can_resume: bool = False
    fields_written: list = field(default_factory=list)
    result: str = ""


_to_character_card_task_result = build_dataclass_result_mapper(
    CharacterCardTaskResult,
    {
        "success": bool,
        "can_resume": bool,
        "message": lambda v: v or "",
        "fields_written": lambda v: v or [],
        "result": lambda v: v or "",
    },
)


_load_resume_character_card_state = build_resume_state_loader(
    CharacterCardResumeState,
    {
        "fields_data": "fields_data",
        "messages": "messages",
        "iteration_count": "iteration_count",
    },
)
_build_initial_character_card_state = build_initial_state_factory(CharacterCardResumeState)
_from_character_card_payload = build_clean_payload_loader(GenerateCharacterCardRequest)
_build_prepared_character_card_task = build_prepared_state_builder(
    PreparedGenerateCharacterCardTask,
    ("fields_data", "messages", "iteration_count"),
)
_on_character_card_resumed = build_on_resumed_logger(
    lambda _request_data, checkpoint_data, _runtime: (
        f"Resuming generate_chara_card: iteration {checkpoint_data.state.iteration_count}, "
        f"fields: {list(checkpoint_data.state.fields_data.keys())}"
    )
)


def _prepare_generate_character_card_request(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> tuple[PreparedGenerateCharacterCardTask | None, dict[str, Any] | None]:
    """准备角色卡生成请求。

    Args:
        data: 原始请求数据。
        runtime: 任务运行时依赖。

    Returns:
        tuple[PreparedGenerateCharacterCardTask | None, dict[str, Any] | None]: prepared 对象和错误结果。

    Raises:
        Exception: 请求预处理失败时向上抛出。
    """
    return prepare_task_context(
        data=data,
        runtime=runtime,
        from_payload=_from_character_card_payload,
        config_builder=build_llm_config,
        checkpoint_task_type=TASK_TYPE_GENERATE_CHARA_CARD,
        load_resume_state=_load_resume_character_card_state,
        build_initial_state=_build_initial_character_card_state,
        load_resumable_checkpoint_fn=load_resumable_checkpoint,
        build_prepared=_build_prepared_character_card_task,
        on_resumed=_on_character_card_resumed,
    )


def _handle_character_card_failure(
    runtime: TaskRuntimeDependencies,
    checkpoint_id: str,
    result: CharacterCardTaskResult,
) -> dict[str, Any]:
    """处理角色卡失败结果。

    Args:
        runtime: 任务运行时依赖。
        checkpoint_id: checkpoint 标识。
        result: 角色卡任务结果。

    Returns:
        dict[str, Any]: 失败响应数据。

    Raises:
        Exception: checkpoint 更新失败时向上抛出。
    """
    if result.can_resume:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, result.message or '生成失败')
        return fail_task_result(result.message or '生成失败', checkpoint_id=checkpoint_id, can_resume=True)
    return fail_task_result(result.message or '生成失败')


def run_generate_character_card_task(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> dict[str, Any]:
    """执行角色卡生成任务。

    Args:
        data: 任务请求数据。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: 统一任务结果，包含成功数据或失败信息。

    Raises:
        Exception: 文件、模型或图片处理未被内部拦截时向上抛出。
    """
    prepared, error = _prepare_generate_character_card_request(data, runtime)
    if error:
        return error

    request_data = prepared.request_data
    config = prepared.config
    checkpoint_id = prepared.checkpoint_id

    all_character_analyses, all_lorebook_entries, error = load_character_analyses(runtime, request_data.role_name)
    if error:
        return error

    all_character_analyses = compress_character_analyses(
        all_character_analyses=all_character_analyses,
        request_data=request_data,
        config=config,
        checkpoint_id=checkpoint_id,
        runtime=runtime,
    )

    paths = prepare_output_paths(
        runtime=runtime,
        request_data=request_data,
        checkpoint_id=checkpoint_id,
    )

    llm_interaction = runtime.llm_gateway.create_client(config)
    raw_result = generate_character_card(
        send_message=llm_interaction.send_message,
        tool_gateway=llm_interaction.tool_gateway,
        lang_names=LANG_NAMES,
        format_vndb_section=format_vndb_section,
        role_name=request_data.role_name,
        all_analyses=all_character_analyses,
        all_lorebook_entries=all_lorebook_entries,
        output_path=paths.json_output_path,
        creator=request_data.creator,
        vndb_data=request_data.vndb_data,
        output_language=request_data.output_language,
        checkpoint_id=checkpoint_id,
        ckpt_messages=prepared.messages if request_data.resume_checkpoint_id else None,
        ckpt_fields_data=prepared.fields_data if request_data.resume_checkpoint_id else None,
        ckpt_iteration_count=prepared.iteration_count if request_data.resume_checkpoint_id else None,
        save_llm_state_fn=getattr(runtime.checkpoint_gateway, "save_llm_state", None),
    )
    result = _to_character_card_task_result(raw_result)

    if result.success:
        return finalize_character_card_success(
            runtime=runtime,
            request_data=request_data,
            checkpoint_id=checkpoint_id,
            paths=paths,
            result=result,
        )

    return _handle_character_card_failure(runtime, checkpoint_id, result)
