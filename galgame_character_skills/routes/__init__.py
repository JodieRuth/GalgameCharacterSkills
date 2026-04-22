"""路由注册模块。"""

from .checkpoints import register_checkpoint_routes
from .files import register_file_routes
from .root import register_root_routes
from .summary import register_summary_routes
from .tasks import register_task_routes
from .vndb import register_vndb_routes

__all__ = [
    "register_checkpoint_routes",
    "register_file_routes",
    "register_root_routes",
    "register_summary_routes",
    "register_task_routes",
    "register_vndb_routes",
]
