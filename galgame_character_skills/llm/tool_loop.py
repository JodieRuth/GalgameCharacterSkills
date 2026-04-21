import json

from ..checkpoint import CheckpointManager


def _checkpoint_fields_snapshot(fields_data):
    return {k: v for k, v in fields_data.items() if k != "character_book_entries"}


def _default_save_llm_state(checkpoint_id, **payload):
    mgr = CheckpointManager()
    mgr.save_llm_state(checkpoint_id, **payload)


def _save_checkpoint_state(checkpoint_id, messages, iteration_count, fields_data, save_llm_state_fn, last_response_marker=None):
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


def _apply_write_field_calls(tool_calls, fields_data):
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


def _append_tool_messages(messages, assistant_message):
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
    send_message,
    tool_gateway,
    tools,
    messages,
    fields_data,
    checkpoint_id,
    initial_tool_call_count=0,
    max_tool_calls=50,
    save_llm_state_fn=None,
):
    tool_call_count = initial_tool_call_count
    save_fn = save_llm_state_fn or _default_save_llm_state

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
