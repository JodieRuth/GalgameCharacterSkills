"""通用工具导出模块，汇总运行时、LLM、路径与 VNDB 相关辅助能力。"""

from .app_runtime import open_browser, configure_werkzeug_logging
from .tool_handler import ToolHandler
from .compression_service import compress_summary_files_with_llm, compress_analyses_with_llm
from .input_normalization import extract_file_paths
from .path_utils import get_base_dir, get_resource_path
from .token_utils import estimate_tokens_from_text
from .vndb_utils import load_r18_traits, clean_vndb_data


def __getattr__(name: str):
    if name == "LLMInteraction":
        from ..llm import LLMInteraction

        globals()["LLMInteraction"] = LLMInteraction
        return LLMInteraction
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "open_browser",
    "configure_werkzeug_logging",
    "ToolHandler",
    "LLMInteraction",
    "compress_summary_files_with_llm",
    "compress_analyses_with_llm",
    "extract_file_paths",
    "get_base_dir",
    "get_resource_path",
    "estimate_tokens_from_text",
    "load_r18_traits",
    "clean_vndb_data",
]
