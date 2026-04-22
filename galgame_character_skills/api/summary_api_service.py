"""总结结果查询接口模块，负责角色列表与 summary 文件发现。"""

from typing import Any, Callable

from ..domain import ok_result
from .validators import require_non_empty_field


def scan_summary_roles_result(
    get_summaries_dir: Callable[[], str],
    discover_summary_roles: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """扫描已生成 summary 的角色列表。

    Args:
        get_summaries_dir: summary 根目录获取函数。
        discover_summary_roles: 角色扫描函数。

    Returns:
        dict[str, Any]: 角色扫描结果。

    Raises:
        Exception: 目录扫描失败时向上抛出。
    """
    summaries_dir = get_summaries_dir()
    result = discover_summary_roles(summaries_dir)
    result['success'] = True
    return result


@require_non_empty_field("role_name", "请输入角色名称")
def get_summary_files_result(
    data: dict[str, Any],
    get_summaries_dir: Callable[[], str],
    find_summary_files_for_role: Callable[[str, str, str], list[str]],
) -> dict[str, Any]:
    """获取指定角色的 summary 文件列表。

    Args:
        data: 请求数据。
        get_summaries_dir: summary 根目录获取函数。
        find_summary_files_for_role: summary 文件发现函数。

    Returns:
        dict[str, Any]: summary 文件列表结果。

    Raises:
        Exception: 文件发现失败时向上抛出。
    """
    mode = data.get('mode', 'skills')
    summaries_dir = get_summaries_dir()
    matching_files = find_summary_files_for_role(summaries_dir, data.get('role_name', ''), mode=mode)
    return ok_result(files=matching_files)
