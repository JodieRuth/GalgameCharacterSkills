"""VNDB 查询接口模块，负责请求校验与结果组装。"""

from typing import Any, Callable

from .validators import require_non_empty_field


@require_non_empty_field("vndb_id", "未提供VNDB ID")
def get_vndb_info_result(
    data: dict[str, Any],
    r18_traits: set[str],
    vndb_gateway: Any,
    fetch_vndb_character: Callable[[str, set[str], Any], dict[str, Any]],
) -> dict[str, Any]:
    """获取 VNDB 角色信息。

    Args:
        data: 请求数据。
        r18_traits: 需过滤的 R18 特征集合。
        vndb_gateway: VNDB 网关。
        fetch_vndb_character: VNDB 查询处理函数。

    Returns:
        dict[str, Any]: VNDB 查询结果。

    Raises:
        Exception: VNDB 查询流程失败时向上抛出。
    """
    vndb_id = data.get('vndb_id', '')
    return fetch_vndb_character(vndb_id, r18_traits, vndb_gateway)
