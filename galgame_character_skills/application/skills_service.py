"""技能包生成用例模块，负责构建上下文、执行 tool loop 与落盘后处理。"""

import json
import os
from typing import Any

from ..checkpoint import load_resumable_checkpoint
from .app_container import TaskRuntimeDependencies
from .skills_context import SkillsContextData, build_skill_context
from .task_prepared import PreparedGenerateSkillsTask
from .task_state import SkillsResumeState, build_initial_state_factory, build_resume_state_loader
from .task_result_factory import ok_task_result, fail_task_result
from .tool_loop_runner import ToolLoopRunState, run_checkpointed_tool_loop
from .task_prepare_context import (
    build_on_resumed_logger,
    build_clean_payload_loader,
    build_prepared_state_builder,
    prepare_task_context,
)
from ..files import find_role_summary_markdown_files
from ..config.request_config import build_llm_config
from ..skills import (
    append_vndb_info_to_skill_md,
    create_code_skill_copy,
)
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


def _initialize_skill_generation(
    llm_interaction: Any,
    summaries_text: str,
    request_data: GenerateSkillsRequest,
    resume_checkpoint_id: str | None,
    output_root_dir: str,
) -> tuple[list[Any] | None, list[dict[str, Any]]]:
    """初始化技能生成对话。

    Args:
        llm_interaction: LLM 交互客户端。
        summaries_text: 技能生成上下文文本。
        request_data: 技能生成请求。
        resume_checkpoint_id: 恢复任务的 checkpoint 标识。
        output_root_dir: 输出根目录。

    Returns:
        tuple[list[Any] | None, list[dict[str, Any]]]: 初始消息和工具定义。

    Raises:
        Exception: 初始化提示词或工具失败时向上抛出。
    """
    if not resume_checkpoint_id:
        messages, tools = llm_interaction.generate_skills_folder_init(
            summaries_text,
            request_data.role_name,
            request_data.output_language,
            request_data.vndb_data,
            output_root_dir=output_root_dir,
        )
    else:
        _, tools = llm_interaction.generate_skills_folder_init(
            summaries_text,
            request_data.role_name,
            request_data.output_language,
            request_data.vndb_data,
            output_root_dir=output_root_dir,
        )
        messages = None

    return messages, tools


def _run_tool_call_loop(
    messages: list[Any],
    tools: list[dict[str, Any]],
    all_results: list[Any],
    iteration: int,
    checkpoint_id: str,
    llm_interaction: Any,
    runtime: TaskRuntimeDependencies,
) -> tuple[ToolLoopRunState | None, dict[str, Any] | None]:
    """执行技能生成 tool loop。

    Args:
        messages: 对话消息列表。
        tools: 可用工具定义。
        all_results: 已累积结果。
        iteration: 当前迭代次数。
        checkpoint_id: checkpoint 标识。
        llm_interaction: LLM 交互客户端。
        runtime: 任务运行时依赖。

    Returns:
        tuple[ToolLoopRunState | None, dict[str, Any] | None]: loop 状态和错误结果。

    Raises:
        Exception: tool loop 执行失败时向上抛出。
    """
    def _append_tool_exchange(
        response: Any,
        tool_calls: list[Any],
        messages_ref: list[Any],
        all_results_ref: list[Any],
    ) -> None:
        assistant_message = {
            "role": "assistant",
            "content": response.choices[0].message.content if response.choices[0].message.content else "",
            "tool_calls": [tc if isinstance(tc, dict) else {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            } for tc in tool_calls]
        }
        messages_ref.append(assistant_message)

        for tool_call in tool_calls:
            result = runtime.tool_gateway.handle_tool_call(tool_call)
            all_results_ref.append(result)
            tool_response = {
                "role": "tool",
                "tool_call_id": tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                "content": json.dumps({"success": True, "result": result})
            }
            messages_ref.append(tool_response)

    def _on_send_failed(message: str) -> dict[str, Any]:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, message)
        return fail_task_result(message, checkpoint_id=checkpoint_id, can_resume=True)

    state, error = run_checkpointed_tool_loop(
        messages=messages,
        tools=tools,
        all_results=all_results,
        iteration=iteration,
        max_iterations=20,
        checkpoint_id=checkpoint_id,
        save_llm_state_fn=getattr(runtime.checkpoint_gateway, "save_llm_state", None),
        send_message=lambda msgs, tool_defs: llm_interaction.send_message(msgs, tool_defs, use_counter=False),
        get_tool_calls=llm_interaction.get_tool_response,
        append_tool_exchange=_append_tool_exchange,
        on_send_failed=_on_send_failed,
        failure_message="LLM交互失败",
    )
    if error:
        return None, error

    return ToolLoopRunState(
        messages=state.messages,
        all_results=state.all_results,
        iteration=state.iteration,
    ), None


def _finalize_generate_skills(
    request_data: GenerateSkillsRequest,
    checkpoint_id: str,
    all_results: list[Any],
    runtime: TaskRuntimeDependencies,
) -> dict[str, Any]:
    """完成技能生成任务。

    Args:
        request_data: 技能生成请求。
        checkpoint_id: checkpoint 标识。
        all_results: 已累积结果。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: 统一任务结果。

    Raises:
        Exception: 后处理或落盘失败时向上抛出。
    """
    skills_root_dir = get_workspace_skills_dir()
    runtime.storage_gateway.makedirs(skills_root_dir, exist_ok=True)
    main_skill_dir = os.path.join(skills_root_dir, f"{request_data.role_name}-skill-main")
    skill_md_path = os.path.join(main_skill_dir, "SKILL.md")

    vndb_result = append_vndb_info_to_skill_md(skill_md_path, request_data.vndb_data)
    if vndb_result:
        all_results.append(vndb_result)

    copy_result = create_code_skill_copy(skills_root_dir, request_data.role_name)
    if copy_result:
        all_results.append(copy_result)

    runtime.checkpoint_gateway.mark_completed(checkpoint_id)
    return ok_task_result(
        message=f'技能文件夹生成完成，共执行 {len(all_results)} 次文件写入',
        results=all_results,
        checkpoint_id=checkpoint_id,
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
    init_messages, tools = _initialize_skill_generation(
        llm_interaction=llm_interaction,
        summaries_text=context_data.summaries_text,
        request_data=request_data,
        resume_checkpoint_id=request_data.resume_checkpoint_id,
        output_root_dir=prompt_skills_root_dir,
    )

    if not request_data.resume_checkpoint_id:
        messages = init_messages
        runtime.checkpoint_gateway.update_progress(checkpoint_id, total_steps=20, current_phase='tool_call_loop')

    loop_result, error = _run_tool_call_loop(
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

    return _finalize_generate_skills(
        request_data=request_data,
        checkpoint_id=checkpoint_id,
        all_results=loop_result.all_results,
        runtime=runtime,
    )
