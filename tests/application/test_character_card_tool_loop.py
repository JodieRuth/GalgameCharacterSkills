import types

from galgame_character_skills.application.character_card import tool_loop


def _tool_call(name, arguments, call_id="tc-1"):
    function = types.SimpleNamespace(name=name, arguments=arguments)
    return types.SimpleNamespace(id=call_id, function=function)


def _response_with_tool_calls(tool_calls, content=""):
    message = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def _response_with_content(content):
    message = types.SimpleNamespace(content=content)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def test_run_character_card_tool_loop_success():
    saves = []

    fields = {"name": "Alice", "description": "", "character_book_entries": [{"id": 1}]}
    messages = [{"role": "system", "content": "x"}]
    send_calls = {"count": 0}

    def fake_send_message(msgs, tools=None, use_counter=False):
        send_calls["count"] += 1
        if send_calls["count"] == 1:
            return _response_with_tool_calls(
                [_tool_call("write_field", '{"field_name":"description","content":"desc","is_complete":false}')],
                content="tool phase",
            )
        return _response_with_content('{"name":"Alice2"}')

    class FakeToolGateway:
        @staticmethod
        def parse_llm_json_response(content):
            return {"name": "Alice2"}

    result = tool_loop.run_character_card_tool_loop(
        send_message=fake_send_message,
        tool_gateway=FakeToolGateway(),
        tools=[{"type": "function"}],
        messages=messages,
        fields_data=fields,
        checkpoint_id="ckpt-1",
        initial_tool_call_count=0,
        max_tool_calls=5,
        save_llm_state_fn=lambda checkpoint_id, **kwargs: saves.append((checkpoint_id, kwargs)),
    )

    assert result["success"] is True
    assert fields["description"] == "desc"
    assert fields["name"] == "Alice2"
    assert send_calls["count"] == 2
    assert len(saves) >= 2
    assert "character_book_entries" not in saves[0][1]["fields_data"]


def test_run_character_card_tool_loop_failure_with_resume_flag():
    saves = []

    result = tool_loop.run_character_card_tool_loop(
        send_message=lambda msgs, tools=None, use_counter=False: None,
        tool_gateway=types.SimpleNamespace(parse_llm_json_response=lambda x: {}),
        tools=[{"type": "function"}],
        messages=[{"role": "system", "content": "x"}],
        fields_data={"name": "A", "character_book_entries": []},
        checkpoint_id="ckpt-2",
        initial_tool_call_count=0,
        max_tool_calls=3,
        save_llm_state_fn=lambda checkpoint_id, **kwargs: saves.append(kwargs),
    )

    assert result == {"success": False, "message": "LLM交互失败", "can_resume": True}
    assert any("last_response" in call and call["last_response"] is None for call in saves)


def test_run_character_card_tool_loop_uses_injected_save_fn():
    saves = []

    result = tool_loop.run_character_card_tool_loop(
        send_message=lambda msgs, tools=None, use_counter=False: _response_with_content('{"name":"A"}'),
        tool_gateway=types.SimpleNamespace(parse_llm_json_response=lambda x: {"name": "A"}),
        tools=[{"type": "function"}],
        messages=[{"role": "system", "content": "x"}],
        fields_data={"name": "", "character_book_entries": []},
        checkpoint_id="ckpt-3",
        initial_tool_call_count=0,
        max_tool_calls=3,
        save_llm_state_fn=lambda checkpoint_id, **kwargs: saves.append((checkpoint_id, kwargs)),
    )

    assert result["success"] is True
    assert len(saves) >= 1


def test_run_character_card_tool_loop_requires_save_fn():
    try:
        tool_loop.run_character_card_tool_loop(
            send_message=lambda msgs, tools=None, use_counter=False: _response_with_content('{"name":"A"}'),
            tool_gateway=types.SimpleNamespace(parse_llm_json_response=lambda x: {"name": "A"}),
            tools=[{"type": "function"}],
            messages=[{"role": "system", "content": "x"}],
            fields_data={"name": "", "character_book_entries": []},
            checkpoint_id="ckpt-4",
            initial_tool_call_count=0,
            max_tool_calls=3,
        )
    except ValueError as exc:
        assert str(exc) == "save_llm_state_fn is required for character card tool loop"
    else:
        raise AssertionError("Expected ValueError when save_llm_state_fn is missing")
