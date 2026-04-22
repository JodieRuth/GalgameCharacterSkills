from galgame_character_skills.llm.provider_config import (
    normalize_model_name,
    build_completion_kwargs,
)


def test_normalize_model_name_uses_provider_prefix_from_baseurl():
    assert normalize_model_name("chat-model", "https://api.deepseek.com") == "deepseek/chat-model"
    assert normalize_model_name("chat-model", "https://claude.example.com") == "anthropic/chat-model"
    assert normalize_model_name("chat-model", "https://generativelanguage.googleapis.com") == "google/chat-model"
    assert normalize_model_name("chat-model", "https://api.openai.com") == "openai/chat-model"


def test_normalize_model_name_keeps_prefixed_model():
    assert normalize_model_name("openai/gpt-4.1", "https://api.deepseek.com") == "openai/gpt-4.1"


def test_build_completion_kwargs_adds_optional_fields():
    kwargs = build_completion_kwargs(
        model="google/gemini-2.5-flash",
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function"}],
        apikey="secret",
        baseurl="https://example.com",
    )

    assert kwargs["model"] == "google/gemini-2.5-flash"
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["api_key"] == "secret"
    assert kwargs["api_base"] == "https://example.com"
    assert "safety_settings" in kwargs


def test_build_completion_kwargs_skips_empty_optional_fields():
    kwargs = build_completion_kwargs(
        model="openai/gpt-4.1",
        messages=[],
        tools=None,
    )

    assert "tools" not in kwargs
    assert "tool_choice" not in kwargs
    assert "api_key" not in kwargs
    assert "api_base" not in kwargs
    assert "safety_settings" not in kwargs
