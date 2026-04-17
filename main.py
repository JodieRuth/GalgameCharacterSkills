import webbrowser
import threading
import time
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from utils.file_processor import FileProcessor
from utils.checkpoint_manager import CheckpointManager
from services.summarize_service import run_summarize_task
from services.skills_service import run_generate_skills_task
from services.character_card_service import run_generate_character_card_task
from services.file_api_service import scan_files_result, calculate_tokens_result, slice_file_result
from services.checkpoint_service import (
    list_checkpoints_result,
    get_checkpoint_result,
    delete_checkpoint_result,
    resume_checkpoint_result,
)
from services.summary_discovery import discover_summary_roles, find_summary_files_for_role
from services.input_normalization import extract_file_paths
from services.vndb_service import fetch_vndb_character
from services.vndb_utils import load_r18_traits, clean_vndb_data
from services.image_card_utils import download_vndb_image, embed_json_in_png
from services.path_utils import get_base_dir, get_resource_path
from services.llm_factory import build_llm_client
from services.token_utils import estimate_tokens_from_text
from services.llm_budget import (
    get_model_context_limit as resolve_model_context_limit,
    calculate_compression_threshold as resolve_compression_threshold,
)


def get_model_context_limit(model_name):
    return resolve_model_context_limit(model_name)


def calculate_compression_threshold(context_limit):
    return resolve_compression_threshold(context_limit)


app = Flask(__name__, template_folder=get_resource_path('utils'))
CORS(app)

file_processor = FileProcessor()
ckpt_manager = CheckpointManager()

R18_TRAITS = load_r18_traits(get_base_dir())

class NoRequestFilter:
    def filter(self, record):
        return not (record.getMessage().startswith('127.0.0.1') and 'HTTP' in record.getMessage())

import logging
log = logging.getLogger('werkzeug')
log.addFilter(NoRequestFilter())

def open_browser():
    time.sleep(0.5)
    webbrowser.open('http://127.0.0.1:5000')


def _json_body():
    return request.get_json(silent=True) or {}


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files', methods=['GET'])
def scan_files():
    return jsonify(scan_files_result(file_processor))

@app.route('/api/summaries/roles', methods=['GET'])
def scan_summary_roles():
    script_dir = get_base_dir()
    result = discover_summary_roles(script_dir)
    result['success'] = True
    return jsonify(result)

@app.route('/api/summaries/files', methods=['POST'])
def get_summary_files():
    data = _json_body()
    role_name = data.get('role_name', '')
    mode = data.get('mode', 'skills')
    if not role_name:
        return jsonify({'success': False, 'message': '请输入角色名称'})
    script_dir = get_base_dir()
    matching_files = find_summary_files_for_role(script_dir, role_name, mode=mode)
    return jsonify({
        'success': True,
        'files': matching_files
    })

@app.route('/api/files/tokens', methods=['POST'])
def calculate_tokens():
    return jsonify(calculate_tokens_result(file_processor, _json_body()))


@app.route('/api/context-limit', methods=['POST'])
def get_context_limit():
    data = _json_body()
    model_name = data.get('model_name', '')
    limit = get_model_context_limit(model_name)
    return jsonify({'success': True, 'context_limit': limit})


@app.route('/api/slice', methods=['POST'])
def slice_file():
    return jsonify(slice_file_result(file_processor, _json_body(), extract_file_paths))

@app.route('/api/summarize', methods=['POST'])
def summarize():
    return _do_summarize(_json_body())

def _do_summarize(data):
    result = run_summarize_task(
        data=data,
        file_processor=file_processor,
        ckpt_manager=ckpt_manager,
        clean_vndb_data=clean_vndb_data
    )
    return jsonify(result)

@app.route('/api/skills', methods=['POST'])
def generate_skills():
    return _do_generate_skills(_json_body())

def _do_generate_skills(data):
    role_name = data.get('role_name', '')
    mode = data.get('mode', 'skills')
    
    if not role_name:
        return jsonify({'success': False, 'message': '请输入角色名称'})
    
    if mode == 'chara_card':
        return generate_character_card(data)
    else:
        return generate_skills_folder(data)

def generate_skills_folder(data):
    result = run_generate_skills_task(
        data=data,
        ckpt_manager=ckpt_manager,
        clean_vndb_data=clean_vndb_data,
        get_base_dir=get_base_dir,
        estimate_tokens=estimate_tokens_from_text,
        build_llm_client=build_llm_client
    )
    return jsonify(result)

def generate_character_card(data):
    result = run_generate_character_card_task(
        data=data,
        ckpt_manager=ckpt_manager,
        clean_vndb_data=clean_vndb_data,
        get_base_dir=get_base_dir,
        estimate_tokens=estimate_tokens_from_text,
        build_llm_client=build_llm_client,
        download_vndb_image=download_vndb_image,
        embed_json_in_png=embed_json_in_png
    )
    return jsonify(result)

@app.route('/api/checkpoints', methods=['GET'])
def list_checkpoints():
    task_type = request.args.get('task_type')
    status = request.args.get('status')
    return jsonify(list_checkpoints_result(ckpt_manager, task_type=task_type, status=status))

@app.route('/api/checkpoints/<checkpoint_id>', methods=['GET'])
def get_checkpoint(checkpoint_id):
    return jsonify(get_checkpoint_result(ckpt_manager, checkpoint_id))

@app.route('/api/checkpoints/<checkpoint_id>', methods=['DELETE'])
def delete_checkpoint(checkpoint_id):
    return jsonify(delete_checkpoint_result(ckpt_manager, checkpoint_id))

@app.route('/api/checkpoints/<checkpoint_id>/resume', methods=['POST'])
def resume_checkpoint(checkpoint_id):
    result = resume_checkpoint_result(
        ckpt_manager=ckpt_manager,
        checkpoint_id=checkpoint_id,
        extra_params=_json_body(),
        summarize_handler=lambda data: run_summarize_task(
            data=data,
            file_processor=file_processor,
            ckpt_manager=ckpt_manager,
            clean_vndb_data=clean_vndb_data
        ),
        generate_skills_handler=lambda data: run_generate_skills_task(
            data=data,
            ckpt_manager=ckpt_manager,
            clean_vndb_data=clean_vndb_data,
            get_base_dir=get_base_dir,
            estimate_tokens=estimate_tokens_from_text,
            build_llm_client=build_llm_client
        ),
        generate_chara_card_handler=lambda data: run_generate_character_card_task(
            data=data,
            ckpt_manager=ckpt_manager,
            clean_vndb_data=clean_vndb_data,
            get_base_dir=get_base_dir,
            estimate_tokens=estimate_tokens_from_text,
            build_llm_client=build_llm_client,
            download_vndb_image=download_vndb_image,
            embed_json_in_png=embed_json_in_png
        )
    )
    return jsonify(result)

@app.route('/api/vndb', methods=['POST'])
def get_vndb_info():
    data = _json_body()
    vndb_id = data.get('vndb_id', '')
    result = fetch_vndb_character(vndb_id, R18_TRAITS)
    return jsonify(result)

if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
