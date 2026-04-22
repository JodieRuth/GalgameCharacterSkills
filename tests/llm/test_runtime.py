from types import SimpleNamespace

from galgame_character_skills.llm.runtime import LLMRequestRuntime


def test_set_total_requests_resets_counter():
    runtime = LLMRequestRuntime(total_requests=2)
    runtime._request_count = 9
    runtime.set_total_requests(5)
    assert runtime._total_requests == 5
    assert runtime._request_count == 0


def test_log_request_start_increments_counter_when_enabled(capsys):
    runtime = LLMRequestRuntime(total_requests=2)
    runtime.log_request_start(
        model="openai/m",
        baseurl="http://x",
        apikey="1234567890123",
        messages=[{"role": "user"}],
        tools=[{"type": "function"}],
        use_counter=True,
    )
    output = capsys.readouterr().out
    assert "Request 1/2" in output
    assert "API Key: 1234567890..." in output
    assert "Messages count: 1, Tools: Yes" in output


def test_log_request_start_without_counter(capsys):
    runtime = LLMRequestRuntime(total_requests=2)
    runtime.log_request_start(
        model="openai/m",
        baseurl="",
        apikey="",
        messages=[],
        tools=None,
        use_counter=False,
    )
    output = capsys.readouterr().out
    assert "Request - Model: openai/m, Base URL:" in output
    assert "API Key: None" in output
    assert "Messages count: 0, Tools: No" in output


def test_log_request_success_and_failed_outputs(capsys):
    runtime = LLMRequestRuntime(total_requests=3)
    runtime._request_count = 1
    runtime.log_request_success(use_counter=True)
    runtime.log_request_failed(use_counter=True)
    output = capsys.readouterr().out
    assert "Sent 1 requests, 2/3 remaining" in output
    assert "Sent 1 requests, 2/3 remaining - Failed" in output


def test_log_response_preview_prints_content_and_tool_count(capsys):
    runtime = LLMRequestRuntime()
    message = SimpleNamespace(content="hello", tool_calls=[{"id": "1"}, {"id": "2"}])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    runtime.log_response_preview(response)
    output = capsys.readouterr().out
    assert "Response content preview: hello" in output
    assert "Tool calls: 2" in output


def test_log_response_preview_handles_long_content(capsys):
    runtime = LLMRequestRuntime()
    long_text = "x" * 120
    message = SimpleNamespace(content=long_text, tool_calls=[])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    runtime.log_response_preview(response)
    output = capsys.readouterr().out
    assert "Response content preview:" in output
    assert "..." in output
