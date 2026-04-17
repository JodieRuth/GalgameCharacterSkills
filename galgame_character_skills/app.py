from flask import Flask, render_template, request, jsonify
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
from .api.vndb_service import fetch_vndb_character
from .utils.llm_budget import get_model_context_limit
from .utils.app_runtime import open_browser
from .web import get_template_dir
from .application import (
    build_app_dependencies,
    build_task_runtime,
    get_base_dir,
)


app = Flask(__name__, template_folder=get_template_dir())
CORS(app)

deps = build_app_dependencies()
task_runtime = build_task_runtime(deps)


def _json_body():
    return request.get_json(silent=True) or {}


def _json_response(result):
    return jsonify(result)


def _run_json(handler, *args, **kwargs):
    return _json_response(handler(*args, **kwargs))


def _run_json_with_body(handler, *args, **kwargs):
    return _run_json(handler, _json_body(), *args, **kwargs)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files', methods=['GET'])
def scan_files():
    return _run_json(scan_files_result, deps.file_processor)

@app.route('/api/summaries/roles', methods=['GET'])
def scan_summary_roles():
    return _run_json(scan_summary_roles_result, get_base_dir, discover_summary_roles)

@app.route('/api/summaries/files', methods=['POST'])
def get_summary_files():
    return _run_json_with_body(get_summary_files_result, get_base_dir, find_summary_files_for_role)

@app.route('/api/files/tokens', methods=['POST'])
def calculate_tokens():
    return _run_json_with_body(calculate_tokens_result, deps.file_processor)


@app.route('/api/context-limit', methods=['POST'])
def get_context_limit():
    return _run_json_with_body(get_context_limit_result, get_model_context_limit)


@app.route('/api/slice', methods=['POST'])
def slice_file():
    return _run_json_with_body(slice_file_result, deps.file_processor, extract_file_paths)

@app.route('/api/summarize', methods=['POST'])
def summarize():
    return _run_json_with_body(summarize_result, task_runtime)


def _generate_skills_folder(payload):
    return generate_skills_folder_result(data=payload, runtime=task_runtime)


def _generate_character_card(payload):
    return generate_character_card_result(data=payload, runtime=task_runtime)


def _summarize(payload):
    return summarize_result(data=payload, runtime=task_runtime)

@app.route('/api/skills', methods=['POST'])
def generate_skills():
    return _run_json_with_body(
        generate_skills_result,
        generate_skills_folder_handler=_generate_skills_folder,
        generate_character_card_handler=_generate_character_card
    )

@app.route('/api/checkpoints', methods=['GET'])
def list_checkpoints():
    task_type = request.args.get('task_type')
    status = request.args.get('status')
    return _run_json(list_checkpoints_result, deps.ckpt_manager, task_type=task_type, status=status)

@app.route('/api/checkpoints/<checkpoint_id>', methods=['GET'])
def get_checkpoint(checkpoint_id):
    return _run_json(get_checkpoint_result, deps.ckpt_manager, checkpoint_id)

@app.route('/api/checkpoints/<checkpoint_id>', methods=['DELETE'])
def delete_checkpoint(checkpoint_id):
    return _run_json(delete_checkpoint_result, deps.ckpt_manager, checkpoint_id)

@app.route('/api/checkpoints/<checkpoint_id>/resume', methods=['POST'])
def resume_checkpoint(checkpoint_id):
    return _run_json_with_body(
        resume_checkpoint_with_payload_result,
        checkpoint_id,
        deps.ckpt_manager,
        _summarize,
        _generate_skills_folder,
        _generate_character_card
    )

@app.route('/api/vndb', methods=['POST'])
def get_vndb_info():
    return _run_json_with_body(get_vndb_info_result, deps.r18_traits, task_runtime.vndb_gateway, fetch_vndb_character)


def create_app():
    return app
