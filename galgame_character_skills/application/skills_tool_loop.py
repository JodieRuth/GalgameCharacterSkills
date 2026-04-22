"""技能生成 tool loop 模块，负责初始化对话与执行工具调用循环。"""

import json
from typing import Any

from .app_container import TaskRuntimeDependencies
from .tool_loop_runner import ToolLoopRunState, run_checkpointed_tool_loop
from .task_result_factory import fail_task_result
from ..domain import GenerateSkillsRequest
from ..llm.message_flows import build_skills_init_messages
from ..llm.shared import LANG_NAMES, format_vndb_section


def initialize_skill_generation(
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
        messages, tools = build_skills_init_messages(
            lang_names=LANG_NAMES,
            format_vndb_section=format_vndb_section,
            summaries=summaries_text,
            role_name=request_data.role_name,
            output_language=request_data.output_language,
            vndb_data=request_data.vndb_data,
            output_root_dir=output_root_dir,
        )
    else:
        _, tools = build_skills_init_messages(
            lang_names=LANG_NAMES,
            format_vndb_section=format_vndb_section,
            summaries=summaries_text,
            role_name=request_data.role_name,
            output_language=request_data.output_language,
            vndb_data=request_data.vndb_data,
            output_root_dir=output_root_dir,
        )
        messages = None

    return messages, tools


def run_skill_tool_loop(
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
                "tool_call_id": tool_call.id if hasattr(tool_call, "id") else tool_call.get("id"),
                "content": json.dumps({"success": True, "result": result}),
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


__all__ = ["initialize_skill_generation", "run_skill_tool_loop"]
