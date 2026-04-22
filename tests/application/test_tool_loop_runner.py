from types import SimpleNamespace

from galgame_character_skills.application.tool_loop_runner import run_checkpointed_tool_loop


def _response_with_tool_calls():
    msg = SimpleNamespace(content="tool", tool_calls=[SimpleNamespace(id="tc-1", function=SimpleNamespace(name="x", arguments="{}"))])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _response_without_tool_calls():
    msg = SimpleNamespace(content="done", tool_calls=[])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_run_checkpointed_tool_loop_success_with_tool_exchange():
    saves = []
    exchanges = []
    gateway = SimpleNamespace(save_llm_state=lambda checkpoint_id, **kwargs: saves.append((checkpoint_id, kwargs)))

    responses = [_response_with_tool_calls(), _response_without_tool_calls()]
    call_idx = {"i": 0}

    def send_message(messages, tools):
        i = call_idx["i"]
        call_idx["i"] += 1
        return responses[i]

    def get_tool_calls(response):
        return response.choices[0].message.tool_calls

    def append_tool_exchange(response, tool_calls, messages, all_results):
        exchanges.append((response, tool_calls))
        messages.append({"role": "assistant", "tool_calls_count": len(tool_calls)})
        all_results.append("ok")

    result, error = run_checkpointed_tool_loop(
        messages=[],
        tools=[{"type": "function"}],
        all_results=[],
        iteration=0,
        max_iterations=5,
        checkpoint_gateway=gateway,
        checkpoint_id="ckpt-1",
        send_message=send_message,
        get_tool_calls=get_tool_calls,
        append_tool_exchange=append_tool_exchange,
        on_send_failed=lambda message: {"success": False, "message": message},
    )

    assert error is None
    assert result.iteration == 2
    assert result.all_results == ["ok"]
    assert len(exchanges) == 1
    assert len(saves) >= 2


def test_run_checkpointed_tool_loop_returns_error_when_send_fails():
    saves = []
    gateway = SimpleNamespace(save_llm_state=lambda checkpoint_id, **kwargs: saves.append(kwargs))

    result, error = run_checkpointed_tool_loop(
        messages=[],
        tools=[],
        all_results=[],
        iteration=0,
        max_iterations=3,
        checkpoint_gateway=gateway,
        checkpoint_id="ckpt-2",
        send_message=lambda _messages, _tools: None,
        get_tool_calls=lambda _response: [],
        append_tool_exchange=lambda *_: None,
        on_send_failed=lambda message: {"success": False, "message": message, "can_resume": True},
    )

    assert result is None
    assert error == {"success": False, "message": "LLM交互失败", "can_resume": True}
    assert any("last_response" in payload and payload["last_response"] is None for payload in saves)


def test_run_checkpointed_tool_loop_stops_when_no_tool_calls():
    gateway = SimpleNamespace(save_llm_state=lambda checkpoint_id, **kwargs: None)

    result, error = run_checkpointed_tool_loop(
        messages=[],
        tools=[],
        all_results=[],
        iteration=0,
        max_iterations=5,
        checkpoint_gateway=gateway,
        checkpoint_id="ckpt-3",
        send_message=lambda _messages, _tools: _response_without_tool_calls(),
        get_tool_calls=lambda response: response.choices[0].message.tool_calls,
        append_tool_exchange=lambda *_: (_ for _ in ()).throw(AssertionError("should not append exchange")),
        on_send_failed=lambda message: {"success": False, "message": message},
    )

    assert error is None
    assert result.iteration == 1
    assert result.all_results == []


def test_run_checkpointed_tool_loop_supports_injected_save_fn_without_gateway():
    saves = []

    result, error = run_checkpointed_tool_loop(
        messages=[],
        tools=[],
        all_results=[],
        iteration=0,
        max_iterations=2,
        checkpoint_id="ckpt-4",
        save_llm_state_fn=lambda checkpoint_id, **kwargs: saves.append((checkpoint_id, kwargs)),
        send_message=lambda _messages, _tools: _response_without_tool_calls(),
        get_tool_calls=lambda response: response.choices[0].message.tool_calls,
        append_tool_exchange=lambda *_: None,
        on_send_failed=lambda message: {"success": False, "message": message},
    )

    assert error is None
    assert result.iteration == 1
    assert saves and saves[0][0] == "ckpt-4"
