"""技能包生成用例模块，负责构建上下文、执行 tool loop 与落盘后处理。"""

from typing import Any

from ..checkpoint import load_resumable_checkpoint
from .app_container import TaskRuntimeDependencies
from .skills_context import SkillsContextData, build_skill_context
from .skills_finalize import finalize_generate_skills
from .skills_tool_loop import initialize_skill_generation, run_skill_tool_loop
from .task_prepared import PreparedGenerateSkillsTask
from .task_state import SkillsResumeState, build_initial_state_factory, build_resume_state_loader
from .task_result_factory import fail_task_result
from .task_prepare_context import (
    build_on_resumed_logger,
    build_clean_payload_loader,
    build_prepared_state_builder,
    prepare_task_context,
)
from ..files import find_role_summary_markdown_files
from ..config.request_config import build_llm_config
from ..domain import GenerateSkillsRequest, fail_result
from ..workspace import get_workspace_skills_dir, get_workspace_summaries_dir


_load_resume_skills_state = build_resume_state_loader(
    SkillsResumeState,
    {
        "messages": "messages",
        "all_results": "all_results",
        "iteration": "iteration_count",
    },
)
_build_initial_skills_state = build_initial_state_factory(SkillsResumeState)
_from_skills_payload = build_clean_payload_loader(GenerateSkillsRequest)
_build_prepared_skills_task = build_prepared_state_builder(
    PreparedGenerateSkillsTask,
    ("messages", "all_results", "iteration"),
)
_on_skills_resumed = build_on_resumed_logger(
    lambda _request_data, checkpoint_data, _runtime: (
        f"Resuming generate_skills: iteration {checkpoint_data.state.iteration}, "
        f"{len(checkpoint_data.state.all_results)} results so far"
    )
)

def _prepare_generate_skills_request(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> tuple[PreparedGenerateSkillsTask | None, dict[str, Any] | None]:
    """准备技能生成请求。

    Args:
        data: 原始请求数据。
        runtime: 任务运行时依赖。

    Returns:
        tuple[PreparedGenerateSkillsTask | None, dict[str, Any] | None]: prepared 对象和错误结果。

    Raises:
        Exception: 请求预处理失败时向上抛出。
    """
    return prepare_task_context(
        data=data,
        runtime=runtime,
        from_payload=_from_skills_payload,
        config_builder=build_llm_config,
        checkpoint_task_type="generate_skills",
        load_resume_state=_load_resume_skills_state,
        build_initial_state=_build_initial_skills_state,
        load_resumable_checkpoint_fn=load_resumable_checkpoint,
        build_prepared=_build_prepared_skills_task,
        on_resumed=_on_skills_resumed,
    )


def run_generate_skills_task(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> dict[str, Any]:
    """执行技能包生成任务。

    Args:
        data: 任务请求数据。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: 统一任务结果，包含成功数据或失败信息。

    Raises:
        Exception: 文件、模型或 checkpoint 操作未被内部拦截时向上抛出。
    """
    prepared, error = _prepare_generate_skills_request(data, runtime)
    if error:
        return error

    request_data = prepared.request_data
    config = prepared.config
    checkpoint_id = prepared.checkpoint_id
    messages = prepared.messages
    all_results = prepared.all_results
    iteration = prepared.iteration

    summaries_root_dir = get_workspace_summaries_dir()
    summary_files = find_role_summary_markdown_files(summaries_root_dir, request_data.role_name)
    if not summary_files:
        return fail_result(f'未找到角色 "{request_data.role_name}" 的归纳文件，请先完成归纳')

    skills_root_dir = get_workspace_skills_dir()
    runtime.storage_gateway.makedirs(skills_root_dir, exist_ok=True)
    prompt_skills_root_dir = skills_root_dir.replace("\\", "/")

    context_data, error = build_skill_context(
        summary_files=summary_files,
        request_data=request_data,
        config=config,
        checkpoint_id=checkpoint_id,
        runtime=runtime,
    )
    if error:
        return error

    llm_interaction = runtime.llm_gateway.create_client(config)
    init_messages, tools = initialize_skill_generation(
        llm_interaction=llm_interaction,
        summaries_text=context_data.summaries_text,
        request_data=request_data,
        resume_checkpoint_id=request_data.resume_checkpoint_id,
        output_root_dir=prompt_skills_root_dir,
    )

    if not request_data.resume_checkpoint_id:
        messages = init_messages
        runtime.checkpoint_gateway.update_progress(checkpoint_id, total_steps=20, current_phase='tool_call_loop')

    loop_result, error = run_skill_tool_loop(
        messages=messages,
        tools=tools,
        all_results=all_results,
        iteration=iteration,
        checkpoint_id=checkpoint_id,
        llm_interaction=llm_interaction,
        runtime=runtime,
    )
    if error:
        return error

    return finalize_generate_skills(
        request_data=request_data,
        checkpoint_id=checkpoint_id,
        all_results=loop_result.all_results,
        runtime=runtime,
    )
