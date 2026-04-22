"""Gateway package with lazy exports."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "LLMGateway",
    "DefaultLLMGateway",
    "ToolGateway",
    "DefaultToolGateway",
    "StorageGateway",
    "DefaultStorageGateway",
    "CheckpointGateway",
    "DefaultCheckpointGateway",
    "VndbGateway",
    "DefaultVndbGateway",
    "ExecutorGateway",
    "DefaultExecutorGateway",
]

_SYMBOL_TO_MODULE = {
    "LLMGateway": ".llm_gateway",
    "DefaultLLMGateway": ".llm_gateway",
    "ToolGateway": ".tool_gateway",
    "DefaultToolGateway": ".tool_gateway",
    "StorageGateway": ".storage_gateway",
    "DefaultStorageGateway": ".storage_gateway",
    "CheckpointGateway": ".checkpoint_gateway",
    "DefaultCheckpointGateway": ".checkpoint_gateway",
    "VndbGateway": ".vndb_gateway",
    "DefaultVndbGateway": ".vndb_gateway",
    "ExecutorGateway": ".executor_gateway",
    "DefaultExecutorGateway": ".executor_gateway",
}

if TYPE_CHECKING:
    from .checkpoint_gateway import CheckpointGateway, DefaultCheckpointGateway
    from .executor_gateway import ExecutorGateway, DefaultExecutorGateway
    from .llm_gateway import LLMGateway, DefaultLLMGateway
    from .storage_gateway import StorageGateway, DefaultStorageGateway
    from .tool_gateway import ToolGateway, DefaultToolGateway
    from .vndb_gateway import VndbGateway, DefaultVndbGateway


def __getattr__(name: str) -> Any:
    """按名称惰性加载网关符号。

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
