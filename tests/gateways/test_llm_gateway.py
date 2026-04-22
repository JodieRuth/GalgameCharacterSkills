from galgame_character_skills.gateways.llm_gateway import DefaultLLMGateway


def test_llm_gateway_delegates_client_creation(monkeypatch):
    captured = {}

    def fake_build(config=None, request_runtime=None):
        captured["config"] = config
        captured["request_runtime"] = request_runtime
        return {"client": True}

    monkeypatch.setattr("galgame_character_skills.gateways.llm_gateway.build_llm_client", fake_build)

    gateway = DefaultLLMGateway()
    result = gateway.create_client(config={"model": "x"}, request_runtime="rt")

    assert result == {"client": True}
    assert captured["config"] == {"model": "x"}
    assert captured["request_runtime"] == "rt"


def test_llm_gateway_creates_request_runtime(monkeypatch):
    captured = {}

    def fake_build_runtime(total_requests=0):
        captured["total"] = total_requests
        return {"runtime": total_requests}

    monkeypatch.setattr(
        "galgame_character_skills.gateways.llm_gateway.LLMInteraction.build_runtime",
        fake_build_runtime,
    )

    gateway = DefaultLLMGateway()
    runtime = gateway.create_request_runtime(42)

    assert captured["total"] == 42
    assert runtime == {"runtime": 42}
