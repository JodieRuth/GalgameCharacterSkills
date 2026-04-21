"""通用工具导出模块，汇总运行时、LLM、路径与 VNDB 相关辅助能力。"""

from .app_runtime import open_browser, configure_werkzeug_logging
from .tool_handler import ToolHandler
from .compression_service import compress_summary_files_with_llm, compress_analyses_with_llm
from .image_card_utils import download_vndb_image, embed_json_in_png
from .input_normalization import extract_file_paths
from .path_utils import get_base_dir, get_resource_path
from .request_config import build_llm_config
from .token_utils import estimate_tokens_from_text
from .vndb_utils import load_r18_traits, clean_vndb_data


def __getattr__(name: str):
    if name == "build_llm_client":
        from .llm_factory import build_llm_client

        globals()["build_llm_client"] = build_llm_client
        return build_llm_client
    if name == "LLMInteraction":
        from ..llm import LLMInteraction

        globals()["LLMInteraction"] = LLMInteraction
        return LLMInteraction
    if name in {"get_model_context_limit", "calculate_compression_threshold"}:
        from .llm_budget import get_model_context_limit, calculate_compression_threshold

        globals()["get_model_context_limit"] = get_model_context_limit
        globals()["calculate_compression_threshold"] = calculate_compression_threshold
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "open_browser",
    "configure_werkzeug_logging",
    "ToolHandler",
    "LLMInteraction",
    "compress_summary_files_with_llm",
    "compress_analyses_with_llm",
    "download_vndb_image",
    "embed_json_in_png",
    "extract_file_paths",
    "get_model_context_limit",
    "calculate_compression_threshold",
    "build_llm_client",
    "get_base_dir",
    "get_resource_path",
    "build_llm_config",
    "estimate_tokens_from_text",
    "load_r18_traits",
    "clean_vndb_data",
]
