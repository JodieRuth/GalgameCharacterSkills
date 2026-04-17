from dataclasses import dataclass

from ..utils.app_runtime import configure_werkzeug_logging
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.file_processor import FileProcessor
from ..utils.image_card_utils import download_vndb_image, embed_json_in_png
from ..utils.llm_factory import build_llm_client
from ..utils.path_utils import get_base_dir
from ..utils.token_utils import estimate_tokens_from_text
from ..utils.vndb_utils import load_r18_traits, clean_vndb_data


@dataclass(frozen=True)
class AppDependencies:
    file_processor: FileProcessor
    ckpt_manager: CheckpointManager
    r18_traits: set


def build_app_dependencies():
    configure_werkzeug_logging()
    return AppDependencies(
        file_processor=FileProcessor(),
        ckpt_manager=CheckpointManager(),
        r18_traits=load_r18_traits(get_base_dir()),
    )


__all__ = [
    "AppDependencies",
    "build_app_dependencies",
    "get_base_dir",
    "clean_vndb_data",
    "estimate_tokens_from_text",
    "build_llm_client",
    "download_vndb_image",
    "embed_json_in_png",
]
