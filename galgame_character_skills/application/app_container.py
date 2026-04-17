from dataclasses import dataclass
from typing import Callable, Any

from ..utils.app_runtime import configure_werkzeug_logging
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.file_processor import FileProcessor
from ..utils.image_card_utils import download_vndb_image, embed_json_in_png
from ..utils.path_utils import get_base_dir
from ..utils.token_utils import estimate_tokens_from_text
from ..utils.vndb_utils import load_r18_traits, clean_vndb_data
from ..gateways.llm_gateway import DefaultLLMGateway, LLMGateway
from ..gateways.tool_gateway import DefaultToolGateway, ToolGateway
from ..gateways.storage_gateway import DefaultStorageGateway, StorageGateway
from ..gateways.checkpoint_gateway import DefaultCheckpointGateway, CheckpointGateway
from ..gateways.vndb_gateway import DefaultVndbGateway, VndbGateway
from ..gateways.executor_gateway import DefaultExecutorGateway, ExecutorGateway


@dataclass(frozen=True)
class AppDependencies:
    file_processor: FileProcessor
    ckpt_manager: CheckpointManager
    r18_traits: set


@dataclass(frozen=True)
class TaskRuntimeDependencies:
    file_processor: FileProcessor
    ckpt_manager: CheckpointManager
    checkpoint_gateway: CheckpointGateway
    storage_gateway: StorageGateway
    vndb_gateway: VndbGateway
    executor_gateway: ExecutorGateway
    clean_vndb_data: Callable[[Any], Any]
    get_base_dir: Callable[[], str]
    estimate_tokens: Callable[[str], int]
    llm_gateway: LLMGateway
    tool_gateway: ToolGateway
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
        checkpoint_gateway=DefaultCheckpointGateway(deps.ckpt_manager),
        storage_gateway=DefaultStorageGateway(),
        vndb_gateway=DefaultVndbGateway(),
        executor_gateway=DefaultExecutorGateway(),
        clean_vndb_data=clean_vndb_data,
        get_base_dir=get_base_dir,
        estimate_tokens=estimate_tokens_from_text,
        llm_gateway=DefaultLLMGateway(),
        tool_gateway=DefaultToolGateway(),
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
    "download_vndb_image",
    "embed_json_in_png",
]
