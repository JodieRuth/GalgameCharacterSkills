"""LLM 子系统导出模块，以惰性导入方式暴露核心交互类。"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = ["LLMInteraction"]

_SYMBOL_TO_MODULE = {
    "LLMInteraction": ".llm_interaction",
}

if TYPE_CHECKING:
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
