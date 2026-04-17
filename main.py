import os
import sys
import webbrowser
import threading
import time
import json
import tiktoken
import math
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
    lines = content.splitlines()
    selected = []
    current_len = 0

    def add_line(line):
        nonlocal current_len
        if not line:
            return
        extra = len(line) + 1
        if current_len + extra > max_chars:
            return
        selected.append(line)
        current_len += extra

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('#', '##', '###', '####', '-', '*', '>', '|')):
            add_line(stripped)

    if current_len < max_chars:
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(('#', '##', '###', '####', '-', '*', '>', '|')):
                continue
            add_line(stripped[:300])
            if current_len >= max_chars:
                break

    if not selected:
        return content[:max_chars]

    result = "\n".join(selected)
    if len(result) < len(content):
        result += "\n[Truncated for context budget]"
    return result


def _extract_key_sections(content, max_chars=8000):
    key_heading_keywords = (
        "核心", "关键", "关系", "经历", "事件", "人格", "语言", "行为",
        "情绪", "设定", "背景", "成长", "矛盾", "identity", "relationship",
        "speech", "behavior", "event", "background", "persona", "emotion"
    )
    lines = content.splitlines()
    sections = []
    current_heading = None
    current_lines = []

    def flush_section():
        if current_heading is not None and current_lines:
            sections.append((current_heading, "\n".join(current_lines).strip()))

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            flush_section()
            current_heading = stripped
            current_lines = [stripped]
        elif current_heading is not None:
            current_lines.append(line)

    flush_section()

    selected = []
    used = 0
    for heading, block in sections:
        if not any(keyword.lower() in heading.lower() for keyword in key_heading_keywords):
            continue
        candidate = block.strip()
        if not candidate:
            continue
        extra = len(candidate) + 2
        if used + extra > max_chars:
            remaining = max_chars - used
            if remaining > 200:
                selected.append(candidate[:remaining].rstrip() + "\n[Truncated key section]")
            break
        selected.append(candidate)
        used += extra

    if not selected:
        return ""
    return "\n\n".join(selected)


def _build_full_skill_generation_context(summary_files):
    sections = []
    for file_path in summary_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        sections.append(f"=== {os.path.basename(file_path)} ===\n{content}")
    return "\n\n".join(sections)


def _head_tail_weighted_order(items):
    ordered = []
    left = 0
    right = len(items) - 1
    pattern = ("head", "tail", "tail")
    step = 0

    while left <= right:
        direction = pattern[step % len(pattern)]
        if direction == "head":
            ordered.append(items[left])
            left += 1
        else:
            ordered.append(items[right])
            right -= 1
        step += 1

    return ordered


def _build_prioritized_skill_generation_context(summary_files, target_total_chars=200000):
    if not summary_files:
        return ""

    file_infos = []
    for file_path in summary_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            file_infos.append({
                "path": file_path,
                "name": os.path.basename(file_path),
                "content": content,
            })
        except Exception:
            continue

    if not file_infos:
        return ""
    sections = []
    used = 0

    def add_section(name, body, suffix=None):
        nonlocal used
        if not body:
            return False
        label = f"=== {name}"
        if suffix:
            label += f" [{suffix}]"
        label += " ===\n"
        candidate = label + body
        extra = len(candidate) + 2
        if used + extra > target_total_chars:
            remaining = target_total_chars - used
            if remaining <= len(label) + 200:
                return False
            body_budget = remaining - len(label)
            candidate = label + body[:body_budget].rstrip() + "\n[Truncated for context budget]"
            extra = len(candidate) + 2
        sections.append(candidate)
        used += extra
        return used < target_total_chars

    prioritized_infos = _head_tail_weighted_order(file_infos)
    full_preserve_count = min(3, len(prioritized_infos))

    for item in prioritized_infos[:full_preserve_count]:
        if not add_section(item["name"], item["content"], suffix="full head-tail weighted"):
            return "\n\n".join(sections)

    for item in prioritized_infos[full_preserve_count:]:
        key_sections = _extract_key_sections(item["content"], max_chars=12000)
        if key_sections:
            if not add_section(item["name"], key_sections, suffix="key sections"):
                return "\n\n".join(sections)

    for item in prioritized_infos[full_preserve_count:]:
        if used >= target_total_chars:
            break
        summary_budget = min(8000, max(2500, (target_total_chars - used) // max(1, len(file_infos))))
        compact = _extract_summary_highlights(item["content"], max_chars=summary_budget)
        add_section(item["name"], compact, suffix="compressed")

    return "\n\n".join(sections)


def _estimate_tokens_from_text(text):
    if not text:
        return 0
    try:
        return len(_tokenizer.encode(text))
    except Exception:
        return max(1, len(text) // 2)


def _compress_with_llm(summary_files, llm_client, target_budget_tokens=115000, checkpoint_id=None):
    print(f"Starting LLM-based compression for {len(summary_files)} files")
    
    total_tokens = 0
    file_contents = {}  
    file_path_map = {}  
    
    for file_path in summary_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            basename = os.path.basename(file_path)
            file_contents[basename] = content
            file_path_map[basename] = file_path
            total_tokens += _estimate_tokens_from_text(content)
        except Exception as e:
            print(f"Warning: Failed to read {file_path}: {e}")
            continue
    
    print(f"Total tokens: {total_tokens}")
    
    if total_tokens <= target_budget_tokens:
        print(f"Total tokens ({total_tokens}) <= target ({target_budget_tokens}), skipping compression")
        return "\n\n".join([f"=== {basename} ===\n{content}" for basename, content in file_contents.items()])
    
    import tempfile
    import shutil
    if checkpoint_id:
        ckpt_temp_dir = ckpt_manager.get_temp_dir(checkpoint_id)
        temp_dir = os.path.join(ckpt_temp_dir, 'llm_compression')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
        temp_base_dir = os.path.join(project_root, 'temp')
        os.makedirs(temp_base_dir, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix='llm_compression_', dir=temp_base_dir)
    temp_file_map = {}  
    
    for basename, original_path in file_path_map.items():
        temp_path = os.path.join(temp_dir, basename)
        shutil.copy2(original_path, temp_path)
        temp_file_map[basename] = temp_path
    
    print(f"Created temp workspace: {temp_dir}")
    
    tokens_per_group = 100000
    num_groups = max(1, math.ceil(total_tokens / tokens_per_group))
    
    files_per_group = math.ceil(len(summary_files) / num_groups)
    
    print(f"Dividing into {num_groups} groups, ~{files_per_group} files per group")
    
    for group_idx in range(num_groups):
        start_idx = group_idx * files_per_group
        end_idx = min((group_idx + 1) * files_per_group, len(summary_files))
        group_files = summary_files[start_idx:end_idx]
        
        if not group_files:
            continue
        
        group_files_content = {}
        group_file_map = {}  
        group_tokens = 0
        for fp in group_files:
            basename = os.path.basename(fp)
            if basename in file_contents:
                group_files_content[basename] = file_contents[basename]
                group_tokens += _estimate_tokens_from_text(file_contents[basename])

                if basename in temp_file_map:
                    group_file_map[basename] = temp_file_map[basename]
        
        print(f"Processing group {group_idx + 1}/{num_groups}: {len(group_files)} files, ~{group_tokens} tokens")
        
        group_info = {
            'group_index': group_idx,
            'total_groups': num_groups,
            'file_count': len(group_files)
        }
        
        messages, tools = llm_client.compress_content_with_llm(group_files_content, group_info)
        
        try:
            max_iterations = 50
            iteration = 0
            total_processed = 0
            
            while iteration < max_iterations:
                iteration += 1
                response = llm_client.send_message(messages, tools, max_retries=2, use_counter=False)
                
                if not response or not hasattr(response, 'choices') or not response.choices:
                    print(f"Warning: LLM returned no response for group {group_idx + 1}, iteration {iteration}")
                    break
                
                message = response.choices[0].message
                
                if not hasattr(message, 'tool_calls') or not message.tool_calls:
                    print(f"Group {group_idx + 1}: No more tool calls after {iteration} iterations")
                    break
                
                tool_results = []
                has_remove_call = False
                
                for tool_call in message.tool_calls:
                    if tool_call.function.name == 'remove_duplicate_sections':
                        has_remove_call = True
                        arguments = json.loads(tool_call.function.arguments)
                        file_sections = arguments.get('file_sections', [])
                        
                        duplicate_tracking = {}
                        
                        for section in file_sections:
                            filename = section.get('filename', '')
                            content = section.get('content', '')
                            if not content or not filename:
                                continue
                            
                            if filename in group_file_map:
                                temp_path = group_file_map[filename]
                                if content not in duplicate_tracking:
                                    duplicate_tracking[content] = []
                                duplicate_tracking[content].append((filename, temp_path))
                        
                        processed_count = 0
                        for content, file_list in duplicate_tracking.items():
                            if len(file_list) <= 1:
                                continue
                            
                            for filename, temp_path in file_list[1:]:
                                try:
                                    with open(temp_path, 'r', encoding='utf-8') as f:
                                        file_content = f.read()
                                    
                                    if content in file_content:
                                        new_content = file_content.replace(content, '')
                                        with open(temp_path, 'w', encoding='utf-8') as f:
                                            f.write(new_content)
                                        processed_count += 1
                                except Exception as e:
                                    print(f"  - Error processing {filename}: {e}")
                        
                        total_processed += processed_count
                        tool_results.append({
                            'tool_call_id': tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                            'result': f"Removed duplicates from {processed_count} files"
                        })
                
                if not has_remove_call:
                    print(f"Warning: LLM did not call remove_duplicate_sections in iteration {iteration}")
                    break
                
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id if hasattr(tc, 'id') else tc.get('id'),
                            "type": "function",
                            "function": {
                                "name": tc.function.name if hasattr(tc, 'function') else tc['function']['name'],
                                "arguments": tc.function.arguments if hasattr(tc, 'function') else tc['function']['arguments']
                            }
                        } for tc in message.tool_calls
                    ]
                })
                
                for result in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": result['tool_call_id'],
                        "content": json.dumps({"status": "success", "message": result['result']})
                    })
                
                print(f"Group {group_idx + 1}, iteration {iteration}: processed {len(tool_results)} tool calls, removed from {total_processed} files so far")
            
            print(f"Group {group_idx + 1} complete: total {total_processed} files modified in {iteration} iterations")
                
        except Exception as e:
            print(f"Error processing group {group_idx + 1}: {e}")
    
    final_content_parts = []
    final_tokens = 0
    for basename in file_contents.keys():
        temp_path = temp_file_map.get(basename)
        if not temp_path:
            continue
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            final_content_parts.append(f"=== {basename} ===\n{content}")
            final_tokens += _estimate_tokens_from_text(content)
        except Exception as e:
            print(f"Warning: Failed to read temp file {temp_path}: {e}")
            final_content_parts.append(f"=== {basename} ===\n{file_contents[basename]}")
            final_tokens += _estimate_tokens_from_text(file_contents[basename])
    
    try:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp workspace: {temp_dir}")
    except Exception as e:
        print(f"Warning: Failed to cleanup temp dir: {e}")
    
    final_content = "\n\n".join(final_content_parts)
    print(f"Final result: {total_tokens} -> {final_tokens} tokens ({final_tokens/total_tokens*100:.1f}%)")
    
    return final_content


def _compress_analyses_with_llm(analyses, llm_client, target_budget_tokens=115000, checkpoint_id=None):
    print(f"Starting compression for {len(analyses)} analyses")
    
    total_tokens = 0
    analysis_contents = {}
    for idx, analysis in enumerate(analyses):
        key = f"analysis_{idx:03d}"
        content = json.dumps(analysis, ensure_ascii=False)
        analysis_contents[key] = content
        total_tokens += _estimate_tokens_from_text(content)
    
    print(f"Total tokens: {total_tokens}")
    
    if total_tokens <= target_budget_tokens:
        print(f"Total tokens ({total_tokens}) <= target ({target_budget_tokens}), skipping compression")
        return analyses
    
    tokens_per_group = 100000
    num_groups = max(1, math.ceil(total_tokens / tokens_per_group))
    
    analyses_per_group = math.ceil(len(analyses) / num_groups)
    
    print(f"Dividing into {num_groups} groups, ~{analyses_per_group} analyses per group")
    
    import tempfile
    import shutil
    if checkpoint_id:
        ckpt_temp_dir = ckpt_manager.get_temp_dir(checkpoint_id)
        temp_dir = os.path.join(ckpt_temp_dir, 'analyses_compression')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
        temp_base_dir = os.path.join(project_root, 'temp')
        os.makedirs(temp_base_dir, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix='analyses_compression_', dir=temp_base_dir)
    temp_file_map = {}
    
    for key, content in analysis_contents.items():
        temp_path = os.path.join(temp_dir, f"{key}.json")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)
        temp_file_map[key] = temp_path
    
    print(f"Created temp workspace: {temp_dir}")
    
    for group_idx in range(num_groups):
        start_idx = group_idx * analyses_per_group
        end_idx = min((group_idx + 1) * analyses_per_group, len(analyses))
        group_keys = list(analysis_contents.keys())[start_idx:end_idx]
        
        if not group_keys:
            continue
        
        group_files_content = {}
        group_file_map = {}  
        group_tokens = 0
        for key in group_keys:
            with open(temp_file_map[key], 'r', encoding='utf-8') as f:
                content = f.read()
            group_files_content[f"{key}.json"] = content
            group_tokens += _estimate_tokens_from_text(content)
            group_file_map[key] = temp_file_map[key]
        
        print(f"Processing group {group_idx + 1}/{num_groups}: {len(group_keys)} analyses, ~{group_tokens} tokens")
        
        group_info = {
            'group_index': group_idx,
            'total_groups': num_groups,
            'file_count': len(group_keys)
        }
        
        messages, tools = llm_client.compress_content_with_llm(group_files_content, group_info)
        
        try:
            max_iterations = 50
            iteration = 0
            total_processed = 0
            
            while iteration < max_iterations:
                iteration += 1
                response = llm_client.send_message(messages, tools, max_retries=2, use_counter=False)
                
                if not response or not hasattr(response, 'choices') or not response.choices:
                    print(f"Warning: LLM returned no response for group {group_idx + 1}, iteration {iteration}")
                    break
                
                message = response.choices[0].message
                
                if not hasattr(message, 'tool_calls') or not message.tool_calls:
                    print(f"Group {group_idx + 1}: No more tool calls after {iteration} iterations")
                    break
                
                tool_results = []
                has_remove_call = False
                
                for tool_call in message.tool_calls:
                    if tool_call.function.name == 'remove_duplicate_sections':
                        has_remove_call = True
                        arguments = json.loads(tool_call.function.arguments)
                        file_sections = arguments.get('file_sections', [])
                        
                        processed_count = 0
                        for section in file_sections:
                            filename = section.get('filename', '')
                            content_to_remove = section.get('content', '')
                            key = filename.replace('.json', '')
                            if key in group_file_map:
                                temp_path = group_file_map[key]
                                try:
                                    with open(temp_path, 'r', encoding='utf-8') as f:
                                        file_content = f.read()
                                    if content_to_remove in file_content:
                                        new_content = file_content.replace(content_to_remove, '')
                                        with open(temp_path, 'w', encoding='utf-8') as f:
                                            f.write(new_content)
                                        processed_count += 1
                                except Exception as e:
                                    print(f"Error processing {filename}: {e}")
                        
                        total_processed += processed_count
                        tool_results.append({
                            'tool_call_id': tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                            'result': f"Removed {processed_count} sections"
                        })
                
                if not has_remove_call:
                    print(f"Warning: LLM did not call remove_duplicate_sections in iteration {iteration}")
                    break
                
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id if hasattr(tc, 'id') else tc.get('id'),
                            "type": "function",
                            "function": {
                                "name": tc.function.name if hasattr(tc, 'function') else tc['function']['name'],
                                "arguments": tc.function.arguments if hasattr(tc, 'function') else tc['function']['arguments']
                            }
                        } for tc in message.tool_calls
                    ]
                })
                
                for result in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": result['tool_call_id'],
                        "content": json.dumps({"status": "success", "message": result['result']})
                    })
                
                print(f"Group {group_idx + 1}, iteration {iteration}: processed {len(tool_results)} tool calls, removed {total_processed} sections so far")
            
            print(f"Group {group_idx + 1} complete: total {total_processed} sections modified in {iteration} iterations")
                
        except Exception as e:
            print(f"Error processing group {group_idx + 1}: {e}")
    
    compressed_analyses = []
    final_tokens = 0
    for idx, key in enumerate(analysis_contents.keys()):
        temp_path = temp_file_map.get(key)
        if not temp_path:
            continue
        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if content.strip():  
                analysis = json.loads(content)
                compressed_analyses.append(analysis)
                final_tokens += _estimate_tokens_from_text(content)
        except Exception as e:
            print(f"Warning: Failed to read temp file {temp_path}: {e}")
            compressed_analyses.append(analyses[idx])
            final_tokens += _estimate_tokens_from_text(analysis_contents[key])
    
    try:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp workspace: {temp_dir}")
    except Exception as e:
        print(f"Warning: Failed to cleanup temp dir: {e}")
    
    print(f"Final result: {len(analyses)} analyses, {total_tokens} -> {final_tokens} tokens ({final_tokens/total_tokens*100:.1f}%)")
    
    return compressed_analyses


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
