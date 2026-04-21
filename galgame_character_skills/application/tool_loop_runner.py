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
    checkpoint_gateway,
    checkpoint_id,
    send_message: Callable[[list, list], Any],
    get_tool_calls: Callable[[Any], Any],
    append_tool_exchange: Callable[[Any, Any, list, list], None],
    on_send_failed: Callable[[str], dict],
    failure_message="LLM交互失败",
):
    while iteration < max_iterations:
        iteration += 1
        checkpoint_gateway.save_llm_state(
            checkpoint_id,
            messages=messages,
            iteration_count=iteration,
            all_results=all_results,
        )

        response = send_message(messages, tools)
        if not response:
            checkpoint_gateway.save_llm_state(
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

        checkpoint_gateway.save_llm_state(
            checkpoint_id,
            messages=messages,
            last_response=response,
            iteration_count=iteration,
            all_results=all_results,
        )

    return ToolLoopRunState(messages=messages, all_results=all_results, iteration=iteration), None


__all__ = ["ToolLoopRunState", "run_checkpointed_tool_loop"]
