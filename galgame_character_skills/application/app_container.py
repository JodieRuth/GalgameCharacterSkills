"""应用依赖装配模块，负责构建全局依赖与任务运行时依赖。"""

import builtins
from dataclasses import dataclass
from typing import Any, Callable

from ..utils.app_runtime import configure_werkzeug_logging
from ..checkpoint import CheckpointManager
from ..files import FileProcessor
from ..character_card import download_vndb_image, embed_json_in_png
from ..utils.path_utils import get_base_dir
from ..utils.token_utils import estimate_tokens_from_text
from ..vndb import load_r18_traits, clean_vndb_data
from ..gateways.llm_gateway import DefaultLLMGateway, LLMGateway
from ..gateways.tool_gateway import DefaultToolGateway, ToolGateway
from ..gateways.storage_gateway import DefaultStorageGateway, StorageGateway
from ..gateways.checkpoint_gateway import DefaultCheckpointGateway, CheckpointGateway
from ..gateways.vndb_gateway import DefaultVndbGateway, VndbGateway
from ..gateways.executor_gateway import DefaultExecutorGateway, ExecutorGateway
from ..workspace import (
    get_workspace_summaries_dir,
    get_workspace_skills_dir,
    get_workspace_cards_dir,
    get_workspace_checkpoints_dir,
)


@dataclass(frozen=True)
class AppDependencies:
    file_processor: FileProcessor
    ckpt_manager: CheckpointManager
    r18_traits: set


@dataclass(frozen=True)
class TaskRuntimeDependencies:
    file_processor: FileProcessor
    checkpoint_gateway: CheckpointGateway
    storage_gateway: StorageGateway
    vndb_gateway: VndbGateway
    executor_gateway: ExecutorGateway
    log: Callable[[str], None]
    clean_vndb_data: Callable[[Any], Any]
    get_base_dir: Callable[[], str]
    get_workspace_summaries_dir: Callable[[], str]
    get_workspace_skills_dir: Callable[[], str]
    get_workspace_cards_dir: Callable[[], str]
    get_workspace_checkpoints_dir: Callable[[], str]
    estimate_tokens: Callable[[str], int]
    llm_gateway: LLMGateway
    tool_gateway: ToolGateway
    download_vndb_image: Callable[[str, str], bool]
    embed_json_in_png: Callable[[dict, str, str], bool]


def build_app_dependencies(
    checkpoint_dir: str | None = None,
    checkpoint_use_singleton: bool = True,
) -> AppDependencies:
    """构建应用级共享依赖。

    Args:
        checkpoint_dir: checkpoint 存储目录。
        checkpoint_use_singleton: 是否复用单例 checkpoint 管理器。

    Returns:
        AppDependencies: 应用级依赖集合。

    Raises:
        Exception: 依赖初始化失败时向上抛出。
    """
    configure_werkzeug_logging()
    return AppDependencies(
        file_processor=FileProcessor(),
        ckpt_manager=CheckpointManager(
            checkpoint_dir=checkpoint_dir,
            use_singleton=checkpoint_use_singleton
        ),
        r18_traits=load_r18_traits(get_base_dir()),
    )


def build_task_runtime(deps: AppDependencies) -> TaskRuntimeDependencies:
    """构建任务运行时依赖。

    Args:
        deps: 应用级共享依赖。

    Returns:
        TaskRuntimeDependencies: 任务执行所需依赖集合。

    Raises:
        Exception: 运行时依赖装配失败时向上抛出。
    """
    return TaskRuntimeDependencies(
        file_processor=deps.file_processor,
        checkpoint_gateway=DefaultCheckpointGateway(deps.ckpt_manager),
        storage_gateway=DefaultStorageGateway(),
        vndb_gateway=DefaultVndbGateway(),
        executor_gateway=DefaultExecutorGateway(),
        log=builtins.print,
        clean_vndb_data=clean_vndb_data,
        get_base_dir=get_base_dir,
        get_workspace_summaries_dir=get_workspace_summaries_dir,
        get_workspace_skills_dir=get_workspace_skills_dir,
        get_workspace_cards_dir=get_workspace_cards_dir,
        get_workspace_checkpoints_dir=get_workspace_checkpoints_dir,
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
    "get_workspace_summaries_dir",
    "get_workspace_skills_dir",
    "get_workspace_cards_dir",
    "get_workspace_checkpoints_dir",
]
