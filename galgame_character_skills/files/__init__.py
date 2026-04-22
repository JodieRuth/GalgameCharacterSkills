"""文件子系统导出模块，暴露文件处理与 summary 发现相关接口。"""

from .processor import FileProcessor
from .summary_discovery import (
    discover_summary_roles,
    find_summary_files_for_role,
    find_role_summary_markdown_files,
    find_role_analysis_summary_file,
)

__all__ = [
    "FileProcessor",
    "discover_summary_roles",
    "find_summary_files_for_role",
    "find_role_summary_markdown_files",
    "find_role_analysis_summary_file",
]
