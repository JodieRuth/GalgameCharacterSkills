"""Top-level package exports with lazy imports."""

from importlib import import_module
from typing import TYPE_CHECKING

__all__ = ["create_app", "open_browser"]

_SYMBOL_TO_MODULE = {
    "create_app": ".app",
    "open_browser": ".utils.app_runtime",
}

if TYPE_CHECKING:
    from .app import create_app
    from .utils.app_runtime import open_browser


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
