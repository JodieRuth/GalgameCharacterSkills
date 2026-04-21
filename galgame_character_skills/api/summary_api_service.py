"""总结结果查询接口模块，负责角色列表与 summary 文件发现。"""

from ..domain import ok_result
from .validators import require_non_empty_field


def scan_summary_roles_result(get_summaries_dir, discover_summary_roles):
    summaries_dir = get_summaries_dir()
    result = discover_summary_roles(summaries_dir)
    result['success'] = True
    return result


@require_non_empty_field("role_name", "请输入角色名称")
def get_summary_files_result(data, get_summaries_dir, find_summary_files_for_role):
    mode = data.get('mode', 'skills')
    summaries_dir = get_summaries_dir()
    matching_files = find_summary_files_for_role(summaries_dir, data.get('role_name', ''), mode=mode)
    return ok_result(files=matching_files)
