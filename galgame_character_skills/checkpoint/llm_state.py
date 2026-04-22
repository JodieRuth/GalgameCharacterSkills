"""Checkpoint LLM 状态持久化模块。"""

from typing import Any

from .store import CheckpointStore


def serialize_llm_response(response: Any) -> dict[str, Any] | None:
    """序列化模型响应对象。"""
    if response is None:
        return None
    try:
        serialized = {
            "id": getattr(response, "id", None),
            "model": getattr(response, "model", None),
            "choices": [],
        }
        if hasattr(response, "choices"):
            for choice in response.choices:
                choice_data = {
                    "index": getattr(choice, "index", 0),
                    "finish_reason": getattr(choice, "finish_reason", None),
                    "message": {
                        "role": getattr(choice.message, "role", "assistant"),
                        "content": getattr(choice.message, "content", None),
                    },
                }
                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                    tool_calls = []
                    for tool_call in choice.message.tool_calls:
                        tool_calls.append(
                            {
                                "id": tool_call.id if hasattr(tool_call, "id") else tool_call.get("id"),
                                "type": tool_call.type if hasattr(tool_call, "type") else tool_call.get("type", "function"),
                                "function": {
                                    "name": tool_call.function.name if hasattr(tool_call, "function") else tool_call["function"]["name"],
                                    "arguments": tool_call.function.arguments if hasattr(tool_call, "function") else tool_call["function"]["arguments"],
                                },
                            }
                        )
                    choice_data["message"]["tool_calls"] = tool_calls
                serialized["choices"].append(choice_data)
        return serialized
    except Exception as exc:
        print(f"Failed to serialize LLM response: {exc}")
        return None


class CheckpointLLMStateService:
    """封装 checkpoint 的 LLM 会话状态读写。"""

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store

    def save_llm_state(
        self,
        checkpoint_id: str,
        messages: list[Any],
        last_response: Any = None,
        iteration_count: int | None = None,
        tool_call_history: list[Any] | None = None,
        all_results: list[Any] | None = None,
        fields_data: dict[str, Any] | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        data = self.store.get_active_checkpoint(checkpoint_id)
        if not data:
            return
        state = data["llm_conversation_state"]
        state["messages"] = messages
        if last_response is not None:
            state["last_response"] = serialize_llm_response(last_response)
        if iteration_count is not None:
            state["iteration_count"] = iteration_count
        if tool_call_history is not None:
            state["tool_call_history"] = tool_call_history
        if all_results is not None:
            state["all_results"] = all_results
        if fields_data is not None:
            state["fields_data"] = fields_data
        if extra_data:
            state.update(extra_data)
        self.store.save_checkpoint(checkpoint_id)

    def load_llm_state(self, checkpoint_id: str) -> dict[str, Any] | None:
        data = self.store.get_active_checkpoint(checkpoint_id)
        if not data:
            return None
        return data["llm_conversation_state"]


__all__ = ["CheckpointLLMStateService", "serialize_llm_response"]
