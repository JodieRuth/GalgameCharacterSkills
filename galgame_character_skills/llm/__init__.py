"""LLM 子系统导出模块，以惰性导入方式暴露核心交互类。"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "LLMInteraction",
    "build_llm_client",
    "get_model_context_limit",
    "calculate_compression_threshold",
    "build_character_card_language_instruction",
    "build_character_card_system_prompt",
    "build_character_card_user_prompt",
    "build_integrate_analyses_system_prompt",
    "build_integrate_analyses_user_prompt",
]

_SYMBOL_TO_MODULE = {
    "LLMInteraction": ".llm_interaction",
    "build_llm_client": ".factory",
    "get_model_context_limit": ".budget",
    "calculate_compression_threshold": ".budget",
    "build_character_card_language_instruction": ".card_prompt_builders",
    "build_character_card_system_prompt": ".card_prompt_builders",
    "build_character_card_user_prompt": ".card_prompt_builders",
    "build_integrate_analyses_system_prompt": ".card_prompt_builders",
    "build_integrate_analyses_user_prompt": ".card_prompt_builders",
}

if TYPE_CHECKING:
    from .budget import calculate_compression_threshold, get_model_context_limit
    from .card_prompt_builders import (
        build_character_card_language_instruction,
        build_character_card_system_prompt,
        build_character_card_user_prompt,
        build_integrate_analyses_system_prompt,
        build_integrate_analyses_user_prompt,
    )
    from .factory import build_llm_client
    from .llm_interaction import LLMInteraction


def __getattr__(name: str) -> Any:
    """按名称惰性加载 LLM 符号。

    Args:
        name: 导出符号名。

    Returns:
        Any: 延迟加载后的符号对象。

    Raises:
        AttributeError: 请求的符号不存在时抛出。
        Exception: 模块导入失败时向上抛出。
    """
    module_path = _SYMBOL_TO_MODULE.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_path, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回模块可见符号列表。

    Args:
        None

    Returns:
        list[str]: 模块符号名列表。

    Raises:
        Exception: 符号列表构造失败时向上抛出。
    """
    return sorted(list(globals().keys()) + __all__)
