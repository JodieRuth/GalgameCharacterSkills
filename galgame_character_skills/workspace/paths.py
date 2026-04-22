"""工作区路径模块，统一管理项目运行期各类目录的定位规则。"""

import os

from ..config.settings import get_app_settings, get_base_dir


def get_workspace_root() -> str:
    """获取工作区根目录。

    Args:
        None

    Returns:
        str: 工作区根目录路径。

    Raises:
        Exception: 路径解析失败时向上抛出。
    """
    settings = get_app_settings()
    workspace_dir = (settings.workspace_dir or "").strip()
    base_dir = get_base_dir()

    if not workspace_dir:
        return os.path.normpath(base_dir)

    if os.path.isabs(workspace_dir):
        return os.path.normpath(workspace_dir)

    return os.path.normpath(os.path.join(base_dir, workspace_dir))


def _workspace_subdir(dirname: str) -> str:
    """构造工作区子目录路径。

    Args:
        dirname: 子目录名。

    Returns:
        str: 子目录路径。

    Raises:
        Exception: 路径拼接失败时向上抛出。
    """
    return os.path.join(get_workspace_root(), dirname)


def get_workspace_uploads_dir() -> str:
    """获取上传目录路径。

    Args:
        None

    Returns:
        str: 上传目录路径。

    Raises:
        Exception: 路径解析失败时向上抛出。
    """
    return _workspace_subdir("uploads")


def get_workspace_summaries_dir() -> str:
    """获取 summary 目录路径。

    Args:
        None

    Returns:
        str: summary 目录路径。

    Raises:
        Exception: 路径解析失败时向上抛出。
    """
    return _workspace_subdir("summaries")


def get_workspace_skills_dir() -> str:
    """获取技能输出目录路径。

    Args:
        None

    Returns:
        str: 技能输出目录路径。

    Raises:
        Exception: 路径解析失败时向上抛出。
    """
    return _workspace_subdir("skills")


def get_workspace_cards_dir() -> str:
    """获取角色卡输出目录路径。

    Args:
        None

    Returns:
        str: 角色卡输出目录路径。

    Raises:
        Exception: 路径解析失败时向上抛出。
    """
    return _workspace_subdir("cards")


def get_workspace_checkpoints_dir() -> str:
    """获取 checkpoint 目录路径。

    Args:
        None

    Returns:
        str: checkpoint 目录路径。

    Raises:
        Exception: 路径解析失败时向上抛出。
    """
    return _workspace_subdir("checkpoints")


__all__ = [
    "get_workspace_root",
    "get_workspace_uploads_dir",
    "get_workspace_summaries_dir",
    "get_workspace_skills_dir",
    "get_workspace_cards_dir",
    "get_workspace_checkpoints_dir",
]
