from types import SimpleNamespace

from galgame_character_skills.utils import llm_budget


def test_get_model_context_limit_returns_default_for_empty_model():
    assert llm_budget.get_model_context_limit("") == 115000


def test_get_model_context_limit_uses_max_input_tokens(monkeypatch):
    fake_litellm = SimpleNamespace(get_model_info=lambda name: {"max_input_tokens": 200000})
    monkeypatch.setattr(
        llm_budget,
        "_get_litellm",
        lambda: fake_litellm,
    )
    assert llm_budget.get_model_context_limit("Model-A") == 200000


def test_get_model_context_limit_falls_back_to_max_tokens(monkeypatch):
    fake_litellm = SimpleNamespace(get_model_info=lambda name: {"max_tokens": 120000})
    monkeypatch.setattr(
        llm_budget,
        "_get_litellm",
        lambda: fake_litellm,
    )
    assert llm_budget.get_model_context_limit("Model-B") == 120000


def test_get_model_context_limit_retries_with_lowercase(monkeypatch):
    called = []

    def fake_get_model_info(name):
        called.append(name)
        if name == "MODEL-X":
            raise RuntimeError("not found")
        return {"max_input_tokens": 131072}

    monkeypatch.setattr(
        llm_budget,
        "_get_litellm",
        lambda: SimpleNamespace(get_model_info=fake_get_model_info),
    )

    assert llm_budget.get_model_context_limit("MODEL-X") == 131072
    assert called == ["MODEL-X", "model-x"]


def test_get_model_context_limit_returns_default_when_all_attempts_fail(monkeypatch):
    fake_litellm = SimpleNamespace(
        get_model_info=lambda name: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    monkeypatch.setattr(
        llm_budget,
        "_get_litellm",
        lambda: fake_litellm,
    )
    assert llm_budget.get_model_context_limit("x") == 115000


def test_calculate_compression_threshold_rules():
    assert llm_budget.calculate_compression_threshold(131074) == int(131074 * 0.8)
    assert llm_budget.calculate_compression_threshold(131073) == int(131073 * 0.85)
