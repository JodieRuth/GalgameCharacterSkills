import os
import sys
import webbrowser
import threading
import time
import json
import tiktoken
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import litellm

from utils.llm_interaction import LLMInteraction
from utils.file_processor import FileProcessor
from utils.checkpoint_manager import CheckpointManager
from services.summarize_service import run_summarize_task
from services.skills_service import run_generate_skills_task
from services.character_card_service import run_generate_character_card_task
from services.summary_discovery import discover_summary_roles, find_summary_files_for_role
from services.checkpoint_utils import load_resumable_checkpoint
from services.input_normalization import extract_file_paths
from services.vndb_service import fetch_vndb_character
from services.image_card_utils import download_vndb_image, embed_json_in_png
from services.compression_service import compress_summary_files_with_llm, compress_analyses_with_llm
from services.skills_context_builder import (
    extract_summary_highlights,
    extract_key_sections,
    build_full_skill_generation_context,
    head_tail_weighted_order,
    build_prioritized_skill_generation_context,
)

_tokenizer = tiktoken.get_encoding("cl100k_base")


def get_model_context_limit(model_name):
    if not model_name:
        return 115000
    
    name_lower = model_name.lower().strip()
    
    for attempt_name in [model_name, name_lower]:
        try:
            model_info = litellm.get_model_info(attempt_name)
            max_tokens = model_info.get("max_input_tokens", model_info.get("max_tokens", None))
            if max_tokens and max_tokens > 0:
                return max_tokens
        except Exception as e:
            continue

    return 115000


def calculate_compression_threshold(context_limit):
    if context_limit > 131073:
        return int(context_limit * 0.80)  
    else:
        return int(context_limit * 0.85)  


def load_r18_traits():
    try:
        base_dir = get_base_dir()
        json_path = os.path.join(base_dir, 'utils', 'r18_traits.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        encoded_traits = data.get('encoded_traits', [])
        return {base64.b64decode(t.encode()).decode('utf-8') for t in encoded_traits}
    except Exception as e:
        print(f"Warning: Failed to load r18_traits: {e}")
        return set()


def clean_vndb_data(vndb_data):
    if vndb_data and isinstance(vndb_data, dict):
        cleaned = vndb_data.copy()
        cleaned.pop('image_url', None)
        return cleaned
    return vndb_data

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

app = Flask(__name__, template_folder=get_resource_path('utils'))
CORS(app)

file_processor = FileProcessor()
ckpt_manager = CheckpointManager()

R18_TRAITS = load_r18_traits()

class NoRequestFilter:
    def filter(self, record):
        return not (record.getMessage().startswith('127.0.0.1') and 'HTTP' in record.getMessage())

import logging
log = logging.getLogger('werkzeug')
log.addFilter(NoRequestFilter())

def open_browser():
    time.sleep(0.5)
    webbrowser.open('http://127.0.0.1:5000')


def _extract_summary_highlights(content, max_chars=5000):
    return extract_summary_highlights(content, max_chars=max_chars)


def _extract_key_sections(content, max_chars=8000):
    return extract_key_sections(content, max_chars=max_chars)


def _build_full_skill_generation_context(summary_files):
    return build_full_skill_generation_context(summary_files)


def _head_tail_weighted_order(items):
    return head_tail_weighted_order(items)


def _build_prioritized_skill_generation_context(summary_files, target_total_chars=200000):
    return build_prioritized_skill_generation_context(summary_files, target_total_chars=target_total_chars)


def _estimate_tokens_from_text(text):
    if not text:
        return 0
    try:
        return len(_tokenizer.encode(text))
    except Exception:
        return max(1, len(text) // 2)


def _compress_with_llm(summary_files, llm_client, target_budget_tokens=115000, checkpoint_id=None):
    return compress_summary_files_with_llm(
        summary_files=summary_files,
        llm_client=llm_client,
        target_budget_tokens=target_budget_tokens,
        checkpoint_id=checkpoint_id,
        ckpt_manager=ckpt_manager,
        estimate_tokens=_estimate_tokens_from_text
    )


def _compress_analyses_with_llm(analyses, llm_client, target_budget_tokens=115000, checkpoint_id=None):
    return compress_analyses_with_llm(
        analyses=analyses,
        llm_client=llm_client,
        target_budget_tokens=target_budget_tokens,
        checkpoint_id=checkpoint_id,
        ckpt_manager=ckpt_manager,
        estimate_tokens=_estimate_tokens_from_text
    )


def build_llm_client(config=None):
    config = config or {}
    baseurl = config.get('baseurl', '')
    modelname = config.get('modelname', '')
    apikey = config.get('apikey', '')
    max_retries = config.get('max_retries', 0) or None
    client = LLMInteraction()
    if baseurl or modelname or apikey:
        client.set_config(baseurl, modelname, apikey, max_retries=max_retries)
    return client


def _json_body():
    return request.get_json(silent=True) or {}


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files', methods=['GET'])
def scan_files():
    files = file_processor.scan_resource_files()
    return jsonify({'success': True, 'files': files})

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
    data = _json_body()
    file_path = data.get('file_path', '')
    slice_size_k = data.get('slice_size_k', 50)
    if not file_path:
        return jsonify({'success': False, 'message': '未提供文件路径'})
    try:
        token_count = file_processor.calculate_tokens(file_path)
        slice_count = file_processor.calculate_slices(token_count, slice_size_k)
        return jsonify({
            'success': True,
            'token_count': token_count,
            'slice_count': slice_count,
            'formatted_tokens': f"{token_count:,}"
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/context-limit', methods=['POST'])
def get_context_limit():
    data = _json_body()
    model_name = data.get('model_name', '')
    limit = get_model_context_limit(model_name)
    return jsonify({'success': True, 'context_limit': limit})


@app.route('/api/slice', methods=['POST'])
def slice_file():
    data = _json_body()
    slice_size_k = data.get('slice_size_k', 50)
    
    file_paths = extract_file_paths(data)
    
    if not file_paths:
        return jsonify({'success': False, 'message': '请先选择文件'})
    
    try:
        slices = file_processor.slice_multiple_files(file_paths, slice_size_k)
        file_count = len(file_paths)
        return jsonify({
            'success': True,
            'message': f'已合并 {file_count} 个文件并切片，共 {len(slices)} 个切片',
            'slice_count': len(slices),
            'file_count': file_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'切片失败: {str(e)}'
        })

@app.route('/api/summarize', methods=['POST'])
def summarize():
    return _do_summarize(_json_body())

def _do_summarize(data):
    result = run_summarize_task(
        data=data,
        file_processor=file_processor,
        ckpt_manager=ckpt_manager,
        build_llm_client=build_llm_client,
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
        build_full_context=_build_full_skill_generation_context,
        estimate_tokens=_estimate_tokens_from_text,
        get_model_context_limit=get_model_context_limit,
        calculate_compression_threshold=calculate_compression_threshold,
        compress_with_llm=_compress_with_llm,
        build_prioritized_context=_build_prioritized_skill_generation_context,
        build_llm_client=build_llm_client
    )
    return jsonify(result)

def generate_character_card(data):
    result = run_generate_character_card_task(
        data=data,
        ckpt_manager=ckpt_manager,
        clean_vndb_data=clean_vndb_data,
        get_base_dir=get_base_dir,
        estimate_tokens=_estimate_tokens_from_text,
        get_model_context_limit=get_model_context_limit,
        calculate_compression_threshold=calculate_compression_threshold,
        compress_analyses_with_llm=_compress_analyses_with_llm,
        build_llm_client=build_llm_client,
        download_vndb_image=download_vndb_image,
        embed_json_in_png=embed_json_in_png
    )
    return jsonify(result)

@app.route('/api/checkpoints', methods=['GET'])
def list_checkpoints():
    task_type = request.args.get('task_type')
    status = request.args.get('status')
    checkpoints = ckpt_manager.list_checkpoints(task_type=task_type, status=status)
    return jsonify({'success': True, 'checkpoints': checkpoints})

@app.route('/api/checkpoints/<checkpoint_id>', methods=['GET'])
def get_checkpoint(checkpoint_id):
    ckpt = ckpt_manager.load_checkpoint(checkpoint_id)
    if not ckpt:
        return jsonify({'success': False, 'message': f'未找到Checkpoint: {checkpoint_id}'})
    llm_state = ckpt_manager.load_llm_state(checkpoint_id)
    return jsonify({'success': True, 'checkpoint': ckpt, 'llm_state': llm_state})

@app.route('/api/checkpoints/<checkpoint_id>', methods=['DELETE'])
def delete_checkpoint(checkpoint_id):
    success = ckpt_manager.delete_checkpoint(checkpoint_id)
    if success:
        return jsonify({'success': True, 'message': 'Checkpoint已删除'})
    return jsonify({'success': False, 'message': f'未找到Checkpoint: {checkpoint_id}'})

@app.route('/api/checkpoints/<checkpoint_id>/resume', methods=['POST'])
def resume_checkpoint(checkpoint_id):
    ckpt, error = load_resumable_checkpoint(ckpt_manager, checkpoint_id)
    if error:
        return jsonify(error)
    
    task_type = ckpt['task_type']
    input_params = dict(ckpt.get('input_params', {}))
    input_params['resume_checkpoint_id'] = checkpoint_id
    
    extra_params = _json_body()
    input_params.update(extra_params)
    
    if task_type == 'summarize':
        return _do_summarize(input_params)
    elif task_type == 'generate_skills':
        return _do_generate_skills(input_params)
    elif task_type == 'generate_chara_card':
        return generate_character_card(input_params)
    else:
        return jsonify({'success': False, 'message': f'未知的任务类型: {task_type}'})

@app.route('/api/vndb', methods=['POST'])
def get_vndb_info():
    data = _json_body()
    vndb_id = data.get('vndb_id', '')
    result = fetch_vndb_character(vndb_id, R18_TRAITS)
    return jsonify(result)

if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
