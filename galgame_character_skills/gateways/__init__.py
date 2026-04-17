"""Gateway package with lazy exports."""

from importlib import import_module
from typing import TYPE_CHECKING

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


def __getattr__(name: str):
    module_path = _SYMBOL_TO_MODULE.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_path, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals().keys()) + __all__)
