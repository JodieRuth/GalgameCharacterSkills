from galgame_character_skills.gateways.llm_gateway import DefaultLLMGateway


def test_llm_gateway_delegates_client_creation(monkeypatch):
    captured = {}

    def fake_build(config=None):
        captured["config"] = config
        return {"client": True}

    monkeypatch.setattr("galgame_character_skills.gateways.llm_gateway.build_llm_client", fake_build)

    gateway = DefaultLLMGateway()
    result = gateway.create_client(config={"model": "x"})

    assert result == {"client": True}
    assert captured["config"] == {"model": "x"}


def test_llm_gateway_delegates_total_requests(monkeypatch):
    captured = {}

    def fake_set_total_requests(total):
        captured["total"] = total

    monkeypatch.setattr(
        "galgame_character_skills.gateways.llm_gateway.LLMInteraction.set_total_requests",
        fake_set_total_requests,
    )

    gateway = DefaultLLMGateway()
    gateway.set_total_requests(42)

    assert captured["total"] == 42
