"""通用 tool loop 执行模块，封装可持久化的循环状态推进逻辑。"""

from dataclasses import dataclass
from typing import Any, Callable

from ..gateways.checkpoint_gateway import CheckpointGateway


@dataclass(frozen=True)
class ToolLoopRunState:
    messages: list
    all_results: list
    iteration: int


def run_checkpointed_tool_loop(
    *,
    messages: list[Any],
    tools: list[dict[str, Any]],
    all_results: list[Any],
    iteration: int,
    max_iterations: int,
    checkpoint_gateway: CheckpointGateway | None = None,
    checkpoint_id: str,
    save_llm_state_fn: Callable[..., Any] | None = None,
    send_message: Callable[[list[Any], list[dict[str, Any]]], Any],
    get_tool_calls: Callable[[Any], Any],
    append_tool_exchange: Callable[[Any, Any, list[Any], list[Any]], None],
    on_send_failed: Callable[[str], dict[str, Any]],
    failure_message: str = "LLM交互失败",
) -> tuple[ToolLoopRunState | None, dict[str, Any] | None]:
    """执行可持久化的 tool loop。

    Args:
        messages: 对话消息列表。
        tools: 可用工具定义。
        all_results: 已累积的工具结果。
        iteration: 当前迭代次数。
        max_iterations: 最大迭代次数。
        checkpoint_gateway: checkpoint 网关。
        checkpoint_id: checkpoint 标识。
        save_llm_state_fn: LLM 状态保存函数。
        send_message: 模型发送函数。
        get_tool_calls: 工具调用提取函数。
        append_tool_exchange: 工具调用结果回写函数。
        on_send_failed: 发送失败结果构造函数。
        failure_message: 默认失败消息。

    Returns:
        tuple[ToolLoopRunState | None, dict[str, Any] | None]: loop 状态和错误结果。

    Raises:
        ValueError: 未提供可用的状态保存函数时抛出。
        Exception: 模型调用或状态保存失败时向上抛出。
    """
    save_fn = save_llm_state_fn or getattr(checkpoint_gateway, "save_llm_state", None)
    if save_fn is None:
        raise ValueError("save_llm_state_fn is required when checkpoint_gateway is not provided")

    while iteration < max_iterations:
        iteration += 1
        save_fn(
            checkpoint_id,
            messages=messages,
            iteration_count=iteration,
            all_results=all_results,
        )

        response = send_message(messages, tools)
        if not response:
            save_fn(
                checkpoint_id,
                messages=messages,
                last_response=None,
                iteration_count=iteration,
                all_results=all_results,
            )
            return None, on_send_failed(failure_message)

        tool_calls = get_tool_calls(response)
        if not tool_calls:
            break

        append_tool_exchange(response, tool_calls, messages, all_results)

        save_fn(
            checkpoint_id,
            messages=messages,
            last_response=response,
            iteration_count=iteration,
            all_results=all_results,
        )

    return ToolLoopRunState(messages=messages, all_results=all_results, iteration=iteration), None


__all__ = ["ToolLoopRunState", "run_checkpointed_tool_loop"]
