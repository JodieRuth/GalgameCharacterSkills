from dataclasses import dataclass
from typing import Callable, Any

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


@dataclass(frozen=True)
class TaskRuntimeDependencies:
    file_processor: FileProcessor
    ckpt_manager: CheckpointManager
    clean_vndb_data: Callable[[Any], Any]
    get_base_dir: Callable[[], str]
    estimate_tokens: Callable[[str], int]
    build_llm_client: Callable[[dict], Any]
    download_vndb_image: Callable[[str, str], bool]
    embed_json_in_png: Callable[[dict, str, str], bool]


def build_app_dependencies():
    configure_werkzeug_logging()
    return AppDependencies(
        file_processor=FileProcessor(),
        ckpt_manager=CheckpointManager(),
        r18_traits=load_r18_traits(get_base_dir()),
    )


def build_task_runtime(deps: AppDependencies):
    return TaskRuntimeDependencies(
        file_processor=deps.file_processor,
        ckpt_manager=deps.ckpt_manager,
        clean_vndb_data=clean_vndb_data,
        get_base_dir=get_base_dir,
        estimate_tokens=estimate_tokens_from_text,
        build_llm_client=build_llm_client,
        download_vndb_image=download_vndb_image,
        embed_json_in_png=embed_json_in_png,
    )


__all__ = [
    "AppDependencies",
    "TaskRuntimeDependencies",
    "build_app_dependencies",
    "build_task_runtime",
    "get_base_dir",
    "clean_vndb_data",
    "estimate_tokens_from_text",
    "build_llm_client",
    "download_vndb_image",
    "embed_json_in_png",
]
