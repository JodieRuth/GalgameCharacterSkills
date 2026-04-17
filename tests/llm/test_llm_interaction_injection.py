from galgame_character_skills.llm.llm_interaction import LLMInteraction


class _FakeRuntime:
    def __init__(self):
        self.events = []

    def log_request_start(self, **kwargs):
        self.events.append(("start", kwargs))

    def log_request_success(self, **kwargs):
        self.events.append(("success", kwargs))

    def log_response_preview(self, response):
        self.events.append(("preview", response))

    def log_request_failed(self, **kwargs):
        self.events.append(("failed", kwargs))


class _FakeTransport:
    def __init__(self):
        self.last_kwargs = None
        self.last_retries = None

    def complete_with_retry(
        self,
        kwargs,
        max_retries,
        on_attempt_failed=None,
        on_retry_wait=None,
        on_success=None,
        on_final_failure=None,
    ):
        self.last_kwargs = kwargs
        self.last_retries = max_retries
        response = {"mock": True}
        if on_success:
            on_success(response)
        return response


def test_llm_interaction_uses_injected_runtime_and_transport():
    runtime = _FakeRuntime()
    transport = _FakeTransport()
    tool_gateway = object()
    client = LLMInteraction(tool_gateway=tool_gateway, transport=transport, runtime=runtime)
    client.set_config(baseurl="https://api.deepseek.com", modelname="chat-model", apikey="secret-key", max_retries=5)

    response = client.send_message(messages=[{"role": "user", "content": "hello"}], tools=None, use_counter=False)

    assert response == {"mock": True}
    assert client.tool_gateway is tool_gateway
    assert transport.last_retries == 5
    assert transport.last_kwargs["model"] == "deepseek/chat-model"
    assert transport.last_kwargs["api_key"] == "secret-key"
    assert transport.last_kwargs["api_base"] == "https://api.deepseek.com"
    assert any(event[0] == "start" for event in runtime.events)
    assert any(event[0] == "success" for event in runtime.events)
    assert any(event[0] == "preview" for event in runtime.events)


def test_set_total_requests_delegates_to_runtime_class():
    class _RuntimeClass:
        called_with = None

        @classmethod
        def set_total_requests(cls, total):
            cls.called_with = total

    original_runtime_cls = LLMInteraction._runtime_cls
    try:
        LLMInteraction._runtime_cls = _RuntimeClass
        LLMInteraction.set_total_requests(11)
        assert _RuntimeClass.called_with == 11
    finally:
        LLMInteraction._runtime_cls = original_runtime_cls
