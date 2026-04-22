"""通用工具导出模块，汇总运行时、LLM、路径与 VNDB 相关辅助能力。"""

from .app_runtime import open_browser, configure_werkzeug_logging
from .input_normalization import extract_file_paths
from .path_utils import get_base_dir, get_resource_path
from .token_utils import estimate_tokens_from_text


def __getattr__(name: str):
    if name == "LLMInteraction":
        from ..llm import LLMInteraction

        globals()["LLMInteraction"] = LLMInteraction
        return LLMInteraction
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "open_browser",
    "configure_werkzeug_logging",
    "LLMInteraction",
    "extract_file_paths",
    "get_base_dir",
    "get_resource_path",
    "estimate_tokens_from_text",
]
