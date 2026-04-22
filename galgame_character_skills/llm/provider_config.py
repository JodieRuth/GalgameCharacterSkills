"""LLM provider 配置辅助函数。"""

from typing import Any


def normalize_model_name(model: str, baseurl: str = "") -> str:
    """根据 baseurl 规范化 provider/model 名称。"""
    normalized_baseurl = baseurl.lower() if baseurl else ""

    if model and "/" not in model:
        if "deepseek" in normalized_baseurl:
            return f"deepseek/{model}"
        if "anthropic" in normalized_baseurl or "claude" in normalized_baseurl:
            return f"anthropic/{model}"
        if "gemini" in normalized_baseurl or "google" in normalized_baseurl:
            return f"google/{model}"
        return f"openai/{model}"
    return model


def build_completion_kwargs(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    apikey: str = "",
    baseurl: str = "",
) -> dict[str, Any]:
    """构造 completion 请求参数。"""
    kwargs = {
        "model": model,
        "messages": messages,
        "timeout": 300,
    }

    if "google" in model or "gemini" in model:
        kwargs["safety_settings"] = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    if apikey:
        kwargs["api_key"] = apikey
    if baseurl:
        kwargs["api_base"] = baseurl
    return kwargs


__all__ = ["normalize_model_name", "build_completion_kwargs"]
