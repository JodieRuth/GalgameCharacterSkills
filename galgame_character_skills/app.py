from flask import Flask, render_template, request
from flask_cors import CORS

from .api.file_api_service import scan_files_result, calculate_tokens_result, slice_file_result
from .api.summary_api_service import scan_summary_roles_result, get_summary_files_result
from .api.context_api_service import get_context_limit_result
from .api.vndb_api_service import get_vndb_info_result
from .api.task_api_service import (
    summarize_result,
    generate_skills_result,
    generate_skills_folder_result,
    generate_character_card_result,
)
from .api.checkpoint_service import (
    list_checkpoints_result,
    get_checkpoint_result,
    delete_checkpoint_result,
    resume_checkpoint_with_payload_result,
)
from .utils.summary_discovery import discover_summary_roles, find_summary_files_for_role
from .utils.input_normalization import extract_file_paths
from .utils.json_adapter import JsonApiAdapter
from .api.vndb_service import fetch_vndb_character
from .utils.llm_budget import get_model_context_limit
from .utils.app_runtime import open_browser
from .web import get_template_dir
from .application import build_app_dependencies, build_task_runtime, get_base_dir
from .config import get_app_settings


def _build_task_handlers(runtime):
    return {
        "summarize": lambda payload: summarize_result(data=payload, runtime=runtime),
        "generate_skills_folder": lambda payload: generate_skills_folder_result(data=payload, runtime=runtime),
        "generate_character_card": lambda payload: generate_character_card_result(data=payload, runtime=runtime),
    }


def _register_root_route(app):
    @app.route("/")
    def index():
        return render_template("index.html")


def _register_file_routes(app, deps, adapter):
    @app.route("/api/files", methods=["GET"])
    def scan_files():
        return adapter.run(scan_files_result, deps.file_processor)

    @app.route("/api/files/tokens", methods=["POST"])
    def calculate_tokens():
        return adapter.run_with_body(lambda data: calculate_tokens_result(deps.file_processor, data))

    @app.route("/api/slice", methods=["POST"])
    def slice_file():
        return adapter.run_with_body(lambda data: slice_file_result(deps.file_processor, data, extract_file_paths))


def _register_summary_routes(app, adapter):
    @app.route("/api/summaries/roles", methods=["GET"])
    def scan_summary_roles():
        return adapter.run(scan_summary_roles_result, get_base_dir, discover_summary_roles)

    @app.route("/api/summaries/files", methods=["POST"])
    def get_summary_files():
        return adapter.run_with_body(get_summary_files_result, get_base_dir, find_summary_files_for_role)

    @app.route("/api/context-limit", methods=["POST"])
    def get_context_limit():
        return adapter.run_with_body(get_context_limit_result, get_model_context_limit)


def _register_task_routes(app, runtime, adapter, task_handlers):
    @app.route("/api/summarize", methods=["POST"])
    def summarize():
        return adapter.run_with_body(summarize_result, runtime)

    @app.route("/api/skills", methods=["POST"])
    def generate_skills():
        return adapter.run_with_body(
            generate_skills_result,
            generate_skills_folder_handler=task_handlers["generate_skills_folder"],
            generate_character_card_handler=task_handlers["generate_character_card"],
        )


def _register_checkpoint_routes(app, runtime, adapter, task_handlers):
    @app.route("/api/checkpoints", methods=["GET"])
    def list_checkpoints():
        task_type = request.args.get("task_type")
        status = request.args.get("status")
        return adapter.run(
            list_checkpoints_result,
            runtime.checkpoint_gateway,
            task_type=task_type,
            status=status,
        )

    @app.route("/api/checkpoints/<checkpoint_id>", methods=["GET"])
    def get_checkpoint(checkpoint_id):
        return adapter.run(get_checkpoint_result, runtime.checkpoint_gateway, checkpoint_id)

    @app.route("/api/checkpoints/<checkpoint_id>", methods=["DELETE"])
    def delete_checkpoint(checkpoint_id):
        return adapter.run(delete_checkpoint_result, runtime.checkpoint_gateway, checkpoint_id)

    @app.route("/api/checkpoints/<checkpoint_id>/resume", methods=["POST"])
    def resume_checkpoint(checkpoint_id):
        return adapter.run_with_body(
            resume_checkpoint_with_payload_result,
            checkpoint_id,
            runtime.checkpoint_gateway,
            task_handlers["summarize"],
            task_handlers["generate_skills_folder"],
            task_handlers["generate_character_card"],
        )


def _register_vndb_route(app, deps, runtime, adapter):
    @app.route("/api/vndb", methods=["POST"])
    def get_vndb_info():
        return adapter.run_with_body(
            get_vndb_info_result,
            deps.r18_traits,
            runtime.vndb_gateway,
            fetch_vndb_character,
        )


def create_app(app_dependencies=None, task_runtime=None):
    # Warm settings cache so .env/env defaults are loaded during startup.
    get_app_settings()
    app = Flask(__name__, template_folder=get_template_dir())
    CORS(app)

    deps = app_dependencies or build_app_dependencies()
    runtime = task_runtime or build_task_runtime(deps)
    adapter = JsonApiAdapter()
    task_handlers = _build_task_handlers(runtime)

    _register_root_route(app)
    _register_file_routes(app, deps, adapter)
    _register_summary_routes(app, adapter)
    _register_task_routes(app, runtime, adapter, task_handlers)
    _register_checkpoint_routes(app, runtime, adapter, task_handlers)
    _register_vndb_route(app, deps, runtime, adapter)

    return app


__all__ = ["create_app", "open_browser"]
