"""角色卡 tool loop 模块，负责字段写入调用、状态保存与循环终止判断。"""

import json
from typing import Any, Callable


def _checkpoint_fields_snapshot(fields_data: dict[str, Any]) -> dict[str, Any]:
    """生成可持久化的字段快照。

    Args:
        fields_data: 当前字段数据。

    Returns:
        dict[str, Any]: 过滤后的字段快照。

    Raises:
        Exception: 快照构造失败时向上抛出。
    """
    return {k: v for k, v in fields_data.items() if k != "character_book_entries"}


def _save_checkpoint_state(
    checkpoint_id: str | None,
    messages: list[Any],
    iteration_count: int,
    fields_data: dict[str, Any],
    save_llm_state_fn: Callable[..., None],
    last_response_marker: Any = None,
) -> None:
    """保存角色卡 tool loop 的 checkpoint 状态。

    Args:
        checkpoint_id: checkpoint 标识。
        messages: 消息列表。
        iteration_count: 当前迭代次数。
        fields_data: 当前字段数据。
        save_llm_state_fn: 状态保存函数。
        last_response_marker: 最近一次响应标记。

    Returns:
        None

    Raises:
        Exception: 状态保存失败时向上抛出。
    """
    if not checkpoint_id:
        return
    payload = {
        "messages": messages,
        "iteration_count": iteration_count,
        "fields_data": _checkpoint_fields_snapshot(fields_data),
    }
    if last_response_marker is not ...:
        payload["last_response"] = last_response_marker
    save_llm_state_fn(checkpoint_id, **payload)


def _apply_write_field_calls(tool_calls: list[Any], fields_data: dict[str, Any]) -> bool:
    """应用 write_field 工具调用结果。

    Args:
        tool_calls: 工具调用列表。
        fields_data: 当前字段数据。

    Returns:
        bool: 是否应强制结束循环。

    Raises:
        Exception: 工具参数解析异常未被内部拦截时向上抛出。
    """
    should_force_complete = False
    for tool_call in tool_calls:
        if tool_call.function.name != "write_field":
            continue
        try:
            args = json.loads(tool_call.function.arguments)
            field_name = args.get("field_name")
            content = args.get("content")
            is_complete = args.get("is_complete", False)

            if field_name in ["creatorcomment", "creator_notes", "world_name"]:
                continue
            if field_name and field_name in fields_data:
                fields_data[field_name] = content
                if is_complete:
                    should_force_complete = True
        except Exception:
            continue
    return should_force_complete


def _append_tool_messages(messages: list[dict[str, Any]], assistant_message: Any) -> None:
    """将工具交互消息追加到会话列表。

    Args:
        messages: 消息列表。
        assistant_message: 助手消息对象。

    Returns:
        None

    Raises:
        Exception: 消息构造失败时向上抛出。
    """
    messages.append(
        {
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in assistant_message.tool_calls
            ],
        }
    )

    for tool_call in assistant_message.tool_calls:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps({"status": "success", "message": "Field written successfully"}),
            }
        )


def run_character_card_tool_loop(
    send_message: Callable[..., Any],
    tool_gateway: Any,
    tools: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    fields_data: dict[str, Any],
    checkpoint_id: str | None,
    initial_tool_call_count: int = 0,
    max_tool_calls: int = 50,
    save_llm_state_fn: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """执行角色卡字段写入 tool loop。

    Args:
        send_message: 模型发送函数。
        tool_gateway: 工具网关。
        tools: 工具定义列表。
        messages: 消息列表。
        fields_data: 当前字段数据。
        checkpoint_id: checkpoint 标识。
        initial_tool_call_count: 初始工具调用次数。
        max_tool_calls: 最大工具调用次数。
        save_llm_state_fn: 状态保存函数。

    Returns:
        dict[str, Any]: tool loop 执行结果。

    Raises:
        ValueError: 未提供状态保存函数时抛出。
        Exception: 模型调用或状态保存失败时向上抛出。
    """
    tool_call_count = initial_tool_call_count
    if save_llm_state_fn is None:
        raise ValueError("save_llm_state_fn is required for character card tool loop")
    save_fn = save_llm_state_fn

    while tool_call_count < max_tool_calls:
        _save_checkpoint_state(
            checkpoint_id=checkpoint_id,
            messages=messages,
            iteration_count=tool_call_count,
            fields_data=fields_data,
            save_llm_state_fn=save_fn,
            last_response_marker=...,
        )

        response = send_message(messages, tools=tools, use_counter=False)

        if not response or not response.choices:
            _save_checkpoint_state(
                checkpoint_id=checkpoint_id,
                messages=messages,
                iteration_count=tool_call_count,
                fields_data=fields_data,
                save_llm_state_fn=save_fn,
                last_response_marker=None,
            )
            return {"success": False, "message": "LLM交互失败", "can_resume": True}

        message = response.choices[0].message

        if hasattr(message, "tool_calls") and message.tool_calls:
            force_complete = _apply_write_field_calls(message.tool_calls, fields_data)
            _append_tool_messages(messages, message)
            tool_call_count += 1
            if force_complete:
                tool_call_count = max_tool_calls
        else:
            content = message.content
            try:
                parsed = tool_gateway.parse_llm_json_response(content)
                if parsed:
                    for key in fields_data.keys():
                        if key in parsed and key != "character_book_entries":
                            fields_data[key] = parsed[key]
            except Exception:
                pass
            break

        _save_checkpoint_state(
            checkpoint_id=checkpoint_id,
            messages=messages,
            iteration_count=tool_call_count,
            fields_data=fields_data,
            save_llm_state_fn=save_fn,
            last_response_marker=response,
        )

    return {"success": True, "messages": messages, "fields_data": fields_data}


__all__ = ["run_character_card_tool_loop"]
