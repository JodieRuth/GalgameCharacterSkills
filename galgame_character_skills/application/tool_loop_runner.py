"""通用 tool loop 执行模块，封装可持久化的循环状态推进逻辑。"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ToolLoopRunState:
    messages: list
    all_results: list
    iteration: int


def run_checkpointed_tool_loop(
    *,
    messages,
    tools,
    all_results,
    iteration,
    max_iterations,
    checkpoint_gateway=None,
    checkpoint_id,
    save_llm_state_fn=None,
    send_message: Callable[[list, list], Any],
    get_tool_calls: Callable[[Any], Any],
    append_tool_exchange: Callable[[Any, Any, list, list], None],
    on_send_failed: Callable[[str], dict],
    failure_message="LLM交互失败",
):
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
