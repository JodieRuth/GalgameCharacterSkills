from importlib import import_module
from typing import TYPE_CHECKING

__all__ = ["LLMInteraction"]

_SYMBOL_TO_MODULE = {
    "LLMInteraction": ".llm_interaction",
}

if TYPE_CHECKING:
    from .llm_interaction import LLMInteraction


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
