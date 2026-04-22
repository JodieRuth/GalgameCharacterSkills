"""Flask 应用入口模块，负责组装运行时依赖并注册路由。"""

from flask import Flask
from flask_cors import CORS

from .application import build_app_dependencies, build_task_runtime
from .config import get_app_settings
from .routes import (
    register_checkpoint_routes,
    register_file_routes,
    register_root_routes,
    register_summary_routes,
    register_task_routes,
    register_vndb_routes,
)
from .utils.app_runtime import open_browser
from .utils.json_adapter import JsonApiAdapter
from .web import get_template_dir


def create_app(app_dependencies=None, task_runtime=None):
    # Warm settings cache so .env/env defaults are loaded during startup.
    get_app_settings()
    app = Flask(__name__, template_folder=get_template_dir())
    CORS(app)

    deps = app_dependencies or build_app_dependencies()
    runtime = task_runtime or build_task_runtime(deps)
    adapter = JsonApiAdapter()

    register_root_routes(app)
    register_file_routes(app, deps, adapter)
    register_summary_routes(app, adapter, get_app_settings)
    register_task_routes(app, runtime, adapter)
    register_checkpoint_routes(app, runtime, adapter)
    register_vndb_routes(app, deps, runtime, adapter)

    return app


__all__ = ["create_app", "open_browser"]
