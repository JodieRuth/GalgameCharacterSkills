"""工作区路径模块，统一管理项目运行期各类目录的定位规则。"""

import os

from ..config.settings import get_app_settings, get_base_dir


def get_workspace_root() -> str:
    settings = get_app_settings()
    workspace_dir = (settings.workspace_dir or "").strip()
    base_dir = get_base_dir()

    if not workspace_dir:
        return os.path.normpath(base_dir)

    if os.path.isabs(workspace_dir):
        return os.path.normpath(workspace_dir)

    return os.path.normpath(os.path.join(base_dir, workspace_dir))


def _workspace_subdir(dirname: str) -> str:
    return os.path.join(get_workspace_root(), dirname)


def get_workspace_uploads_dir() -> str:
    return _workspace_subdir("uploads")


def get_workspace_summaries_dir() -> str:
    return _workspace_subdir("summaries")


def get_workspace_skills_dir() -> str:
    return _workspace_subdir("skills")


def get_workspace_cards_dir() -> str:
    return _workspace_subdir("cards")


def get_workspace_checkpoints_dir() -> str:
    return _workspace_subdir("checkpoints")


__all__ = [
    "get_workspace_root",
    "get_workspace_uploads_dir",
    "get_workspace_summaries_dir",
    "get_workspace_skills_dir",
    "get_workspace_cards_dir",
    "get_workspace_checkpoints_dir",
]
