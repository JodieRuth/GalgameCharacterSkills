"""VNDB 查询接口模块，负责请求校验与结果组装。"""

from .validators import require_non_empty_field


@require_non_empty_field("vndb_id", "未提供VNDB ID")
def get_vndb_info_result(data, r18_traits, vndb_gateway, fetch_vndb_character):
    vndb_id = data.get('vndb_id', '')
    return fetch_vndb_character(vndb_id, r18_traits, vndb_gateway)
