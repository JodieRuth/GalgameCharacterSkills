import os
import sys
import webbrowser
import threading
import time
import json
import requests
import zlib
import base64
import tiktoken
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import litellm

from utils.llm_interaction import LLMInteraction
from utils.file_processor import FileProcessor
from utils.tool_handler import ToolHandler
from utils.checkpoint_manager import CheckpointManager

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
        return int(context_limit * 0.85)  
    else:
        return int(context_limit * 0.90)  


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
current_slices = []
summaries = []

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
                        import json
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
                        import json
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


def get_llm_client():
    data = request.json if request.is_json else {}
    baseurl = data.get('baseurl', '')
    modelname = data.get('modelname', '')
    apikey = data.get('apikey', '')
    client = LLMInteraction()
    if baseurl or modelname or apikey:
        client.set_config(baseurl, modelname, apikey)
    return client

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files', methods=['GET'])
def scan_files():
    files = file_processor.scan_resource_files()
    return jsonify({'success': True, 'files': files})

_last_scan_result = None

@app.route('/api/summaries/roles', methods=['GET'])
def scan_summary_roles():
    global _last_scan_result


    skills_roles = set()  
    chara_card_roles = set()  

    script_dir = get_base_dir()

    for root, dirs, files in os.walk(script_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                summaries_dir = os.path.join(root, dir_name)

                try:
                    dir_files = os.listdir(summaries_dir)

                    for filename in dir_files:
                        if filename.endswith('.md'):
                            parts = filename.replace('.md', '').split('_')
                            if len(parts) >= 3 and parts[0] == 'slice':
                                role_name = '_'.join(parts[2:])
                                if role_name:
                                    skills_roles.add(role_name)

                        elif filename.endswith('_analysis_summary.json'):
                            role_name = filename.replace('_analysis_summary.json', '')
                            if role_name:
                                chara_card_roles.add(role_name)
                except Exception as e:
                    pass

    for root, dirs, files in os.walk(script_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                summaries_dir = os.path.join(root, dir_name)
                try:
                    dir_files = os.listdir(summaries_dir)
                    for filename in dir_files:
                        if filename.startswith('slice_') and filename.endswith('.json'):
                            parts = filename.replace('.json', '').split('_')
                            if len(parts) >= 3:
                                role_name = '_'.join(parts[2:])
                                if role_name:
                                    chara_card_roles.add(role_name)
                except Exception:
                    pass

    all_roles = sorted(list(skills_roles | chara_card_roles))

    result = {
        'success': True,
        'roles': all_roles,
        'skills_roles': sorted(list(skills_roles)),
        'chara_card_roles': sorted(list(chara_card_roles))
    }

    return jsonify(result)

@app.route('/api/summaries/files', methods=['POST'])
def get_summary_files():
    data = request.json
    role_name = data.get('role_name', '')
    mode = data.get('mode', 'skills')
    if not role_name:
        return jsonify({'success': False, 'message': '请输入角色名称'})
    script_dir = get_base_dir()
    matching_files = []
    for root, dirs, files in os.walk(script_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                summaries_dir = os.path.join(root, dir_name)
                for filename in sorted(os.listdir(summaries_dir)):
                    if mode == 'chara_card':
                        if filename.endswith('.json') and f'_{role_name}' in filename:
                            file_path = os.path.join(summaries_dir, filename)
                            matching_files.append(file_path)
                    else:
                        if filename.endswith('.md') and f'_{role_name}.md' in filename:
                            file_path = os.path.join(summaries_dir, filename)
                            matching_files.append(file_path)
    return jsonify({
        'success': True,
        'files': sorted(matching_files)
    })

@app.route('/api/files/tokens', methods=['POST'])
def calculate_tokens():
    data = request.json
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
    data = request.json
    model_name = data.get('model_name', '')
    limit = get_model_context_limit(model_name)
    return jsonify({'success': True, 'context_limit': limit})


@app.route('/api/slice', methods=['POST'])
def slice_file():
    data = request.json
    slice_size_k = data.get('slice_size_k', 50)
    
    file_paths = data.get('file_paths', [])
    if not file_paths:
        single_file = data.get('file_path', '')
        if single_file:
            file_paths = [single_file]
    
    if not file_paths:
        return jsonify({'success': False, 'message': '请先选择文件'})
    
    try:
        global current_slices
        current_slices = file_processor.slice_multiple_files(file_paths, slice_size_k)
        file_count = len(file_paths)
        return jsonify({
            'success': True,
            'message': f'已合并 {file_count} 个文件并切片，共 {len(current_slices)} 个切片',
            'slice_count': len(current_slices),
            'file_count': file_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'切片失败: {str(e)}'
        })

def process_single_slice(args):
    slice_index, slice_content, role_name, instruction, output_file_path, config, output_language, mode, vndb_data, checkpoint_id = args
    llm_client = LLMInteraction()
    if config.get('baseurl') or config.get('modelname') or config.get('apikey'):
        llm_client.set_config(config.get('baseurl'), config.get('modelname'), config.get('apikey'))

    if checkpoint_id:
        existing = ckpt_manager.get_slice_result(checkpoint_id, slice_index)
        if existing:
            print(f"Slice {slice_index} already completed, skipping")
            result = {
                'index': slice_index,
                'success': True,
                'summary': f"Slice {slice_index + 1} restored from checkpoint",
                'tool_results': [],
                'output_path': output_file_path,
                'character_analysis': None,
                'lorebook_entries': [],
                'restored': True
            }
            if mode == 'chara_card':
                try:
                    with open(output_file_path, 'r', encoding='utf-8') as f:
                        parsed = json.load(f)
                    result['character_analysis'] = parsed.get('character_analysis', {})
                    result['lorebook_entries'] = parsed.get('lorebook_entries', [])
                except Exception:
                    pass
            else:
                try:
                    with open(output_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    result['summary'] = content[:200] + "..." if len(content) > 200 else content
                except Exception:
                    pass
            return result

    time.sleep(0.5 * slice_index)
    
    if mode == 'chara_card':
        response = llm_client.summarize_content_for_chara_card(slice_content, role_name, instruction, output_file_path, output_language, vndb_data)
    else:
        response = llm_client.summarize_content(slice_content, role_name, instruction, output_file_path, output_language, vndb_data)
    
    result = {
        'index': slice_index,
        'success': False,
        'summary': None,
        'tool_results': [],
        'output_path': output_file_path,
        'character_analysis': None,
        'lorebook_entries': [],
        'restored': False
    }
    
    if response and hasattr(response, 'choices') and response.choices:
        choice = response.choices[0]
        
        if mode == 'chara_card':
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    tool_result = ToolHandler.handle_tool_call(tool_call)
                    result['tool_results'].append(tool_result)
                result['success'] = True
                result['summary'] = f"Slice {slice_index + 1} saved to {output_file_path}"
                
                try:
                    with open(output_file_path, 'r', encoding='utf-8') as f:
                        parsed = json.load(f)
                    result['character_analysis'] = parsed.get('character_analysis', {})
                    result['lorebook_entries'] = parsed.get('lorebook_entries', [])
                except Exception as e:
                    result['tool_results'].append(f"Warning: Failed to read saved file: {e}")
            
            elif hasattr(choice, 'message') and choice.message.content:
                content = choice.message.content
                parsed = ToolHandler.parse_llm_json_response(content)
                if parsed:
                    result['character_analysis'] = parsed.get('character_analysis', {})
                    result['lorebook_entries'] = parsed.get('lorebook_entries', [])
                    result['success'] = True
                    result['summary'] = f"Slice {slice_index + 1} analyzed successfully"
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        json.dump(parsed, f, ensure_ascii=False, indent=2)
        else:
            if hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    tool_result = ToolHandler.handle_tool_call(tool_call)
                    result['tool_results'].append(tool_result)
                result['success'] = True
                result['summary'] = f"Slice {slice_index + 1} saved to {output_file_path}"
            else:
                result['success'] = True
                result['summary'] = choice.message.content

    if result['success'] and checkpoint_id:
        try:
            if mode == 'chara_card':
                with open(output_file_path, 'r', encoding='utf-8') as f:
                    ckpt_content = f.read()
            else:
                if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                    for tool_call in choice.message.tool_calls:
                        if hasattr(tool_call, 'function') and tool_call.function.name == 'write_file':
                            args_dict = json.loads(tool_call.function.arguments)
                            ckpt_content = args_dict.get('content', '')
                            break
                    else:
                        ckpt_content = result['summary'] or ''
                else:
                    ckpt_content = result['summary'] or ''
            ckpt_manager.save_slice_result(checkpoint_id, slice_index, ckpt_content, 'completed')
            prog = ckpt_manager.load_checkpoint(checkpoint_id)
            if prog:
                completed = prog['progress']['completed_items']
                if slice_index not in completed:
                    completed.append(slice_index)
                pending = [i for i in prog['progress']['pending_items'] if i != slice_index]
                ckpt_manager.update_progress(checkpoint_id, completed_items=completed, pending_items=pending)
        except Exception as e:
            print(f"Failed to save slice {slice_index} result: {e}")
    
    return result


@app.route('/api/summarize', methods=['POST'])
def summarize():
    return _do_summarize(request.json)

def _do_summarize(data):
    global current_slices, summaries
    role_name = data.get('role_name', '')
    instruction = data.get('instruction', '')
    concurrency = data.get('concurrency', 1)
    mode = data.get('mode', 'skills')
    resume_checkpoint_id = data.get('resume_checkpoint_id')
    
    file_paths = data.get('file_paths', [])
    if not file_paths:
        single_file = data.get('file_path', '')
        if single_file:
            file_paths = [single_file]
    
    if not role_name:
        return jsonify({'success': False, 'message': '请输入角色名称'})

    config = {
        'baseurl': data.get('baseurl', ''),
        'modelname': data.get('modelname', ''),
        'apikey': data.get('apikey', '')
    }
    output_language = data.get('output_language', '')
    vndb_data = clean_vndb_data(data.get('vndb_data'))
    slice_size_k = data.get('slice_size_k', 50)

    if resume_checkpoint_id:
        ckpt = ckpt_manager.load_checkpoint(resume_checkpoint_id)
        if not ckpt:
            return jsonify({'success': False, 'message': f'未找到Checkpoint: {resume_checkpoint_id}'})
        if ckpt['status'] == 'completed':
            return jsonify({'success': False, 'message': '该任务已完成，无需恢复'})
        
        role_name = ckpt['input_params'].get('role_name', role_name)
        instruction = ckpt['input_params'].get('instruction', instruction)
        output_language = ckpt['input_params'].get('output_language', output_language)
        mode = ckpt['input_params'].get('mode', mode)
        vndb_data = ckpt['input_params'].get('vndb_data', vndb_data)
        slice_size_k = ckpt['input_params'].get('slice_size_k', slice_size_k)
        file_paths = ckpt['input_params'].get('file_paths', file_paths)
        concurrency = ckpt['input_params'].get('concurrency', concurrency)
        checkpoint_id = resume_checkpoint_id
        
        completed_indices = set(ckpt['progress'].get('completed_items', []))
        print(f"Resuming summarize: {len(completed_indices)}/{ckpt['progress'].get('total_steps', '?')} slices already done")
    else:
        if not file_paths:
            return jsonify({'success': False, 'message': '请先选择文件'})
        
        checkpoint_id = ckpt_manager.create_checkpoint(
            task_type='summarize',
            input_params={
                'role_name': role_name,
                'instruction': instruction,
                'output_language': output_language,
                'mode': mode,
                'vndb_data': vndb_data,
                'slice_size_k': slice_size_k,
                'file_paths': file_paths,
                'concurrency': concurrency
            }
        )

    if not file_paths:
        return jsonify({'success': False, 'message': '请先选择文件'})
    
    llm_interaction = get_llm_client()
    current_slices = file_processor.slice_multiple_files(file_paths, slice_size_k)
    LLMInteraction.set_total_requests(len(current_slices))
    
    summaries = []
    errors = []
    all_results = []
    all_character_analyses = []
    all_lorebook_entries = []
    
    if len(file_paths) == 1:
        file_name = os.path.basename(file_paths[0])
        name, ext = os.path.splitext(file_name)
        summary_dir = os.path.join(os.path.dirname(file_paths[0]), f"{name}_summaries")
    else:
        first_dir = os.path.dirname(file_paths[0])
        name = os.path.basename(file_paths[0])
        name = os.path.splitext(name)[0]
        summary_dir = os.path.join(first_dir, f"{name}_merged_summaries")
    os.makedirs(summary_dir, exist_ok=True)

    if not resume_checkpoint_id:
        ckpt_manager.update_progress(
            checkpoint_id,
            total_steps=len(current_slices),
            pending_items=list(range(len(current_slices)))
        )

    tasks = []
    for i, slice_content in enumerate(current_slices):
        if mode == 'chara_card':
            output_file_path = os.path.join(summary_dir, f"slice_{i+1:03d}_{role_name}.json")
        else:
            output_file_path = os.path.join(summary_dir, f"slice_{i+1:03d}_{role_name}.md")
        tasks.append((i, slice_content, role_name, instruction, output_file_path, config, output_language, mode, vndb_data, checkpoint_id))
    
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_task = {executor.submit(process_single_slice, task): task for task in tasks}
        
        for future in as_completed(future_to_task):
            try:
                result = future.result()
                if result['success']:
                    summaries.append(result['summary'])
                    all_results.extend(result['tool_results'])
                    if result.get('character_analysis'):
                        all_character_analyses.append(result['character_analysis'])
                    if result.get('lorebook_entries'):
                        all_lorebook_entries.append(result['lorebook_entries'])
                else:
                    errors.append(f'切片 {result["index"] + 1} 处理失败')
            except Exception as e:
                task = future_to_task[future]
                errors.append(f'切片 {task[0] + 1} 处理异常: {str(e)}')
    
    if mode == 'chara_card':
        analysis_summary_path = os.path.join(summary_dir, f"{role_name}_analysis_summary.json")
        with open(analysis_summary_path, 'w', encoding='utf-8') as f:
            json.dump({
                'character_analyses': all_character_analyses,
                'lorebook_entries': all_lorebook_entries
            }, f, ensure_ascii=False, indent=2)

    if errors and len(summaries) == 0:
        ckpt_manager.mark_failed(checkpoint_id, f'{len(errors)} 个切片全部失败')
        return jsonify({
            'success': False,
            'message': f'归纳失败，{len(errors)} 个切片失败',
            'slice_count': len(current_slices),
            'errors': errors,
            'results': all_results,
            'checkpoint_id': checkpoint_id,
            'can_resume': True
        })

    if errors:
        ckpt_manager.mark_completed(checkpoint_id)
        return jsonify({
            'success': True,
            'message': f'归纳完成，{len(errors)} 个切片失败',
            'slice_count': len(current_slices),
            'errors': errors,
            'results': all_results,
            'checkpoint_id': checkpoint_id
        })
    
    ckpt_manager.mark_completed(checkpoint_id)
    return jsonify({
        'success': True,
        'message': '归纳完成',
        'slice_count': len(current_slices),
        'results': all_results,
        'checkpoint_id': checkpoint_id
    })

@app.route('/api/skills', methods=['POST'])
def generate_skills():
    return _do_generate_skills(request.json)

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
    role_name = data.get('role_name', '')
    vndb_data = clean_vndb_data(data.get('vndb_data'))
    output_language = data.get('output_language', '')
    compression_mode = data.get('compression_mode', 'original')
    force_no_compression = data.get('force_no_compression', False)
    resume_checkpoint_id = data.get('resume_checkpoint_id')

    if resume_checkpoint_id:
        ckpt = ckpt_manager.load_checkpoint(resume_checkpoint_id)
        if not ckpt:
            return jsonify({'success': False, 'message': f'未找到Checkpoint: {resume_checkpoint_id}'})
        if ckpt['status'] == 'completed':
            return jsonify({'success': False, 'message': '该任务已完成，无需恢复'})
        
        role_name = ckpt['input_params'].get('role_name', role_name)
        vndb_data = ckpt['input_params'].get('vndb_data', vndb_data)
        output_language = ckpt['input_params'].get('output_language', output_language)
        compression_mode = ckpt['input_params'].get('compression_mode', compression_mode)
        force_no_compression = ckpt['input_params'].get('force_no_compression', force_no_compression)
        checkpoint_id = resume_checkpoint_id
        
        llm_state = ckpt_manager.load_llm_state(checkpoint_id)
        messages = llm_state.get('messages', [])
        all_results = llm_state.get('all_results', [])
        iteration = llm_state.get('iteration_count', 0)
        tools = None
        
        print(f"Resuming generate_skills: iteration {iteration}, {len(all_results)} results so far")
    else:
        checkpoint_id = ckpt_manager.create_checkpoint(
            task_type='generate_skills',
            input_params={
                'role_name': role_name,
                'vndb_data': vndb_data,
                'output_language': output_language,
                'compression_mode': compression_mode,
                'force_no_compression': force_no_compression
            }
        )
        messages = []
        all_results = []
        iteration = 0
    
    script_dir = get_base_dir()
    summary_files = []
    for root, dirs, files in os.walk(script_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                summaries_dir = os.path.join(root, dir_name)
                for filename in sorted(os.listdir(summaries_dir)):
                    if filename.endswith('.md') and f'_{role_name}.md' in filename:
                        file_path = os.path.join(summaries_dir, filename)
                        summary_files.append(file_path)
    if not summary_files:
        return jsonify({'success': False, 'message': f'未找到角色 "{role_name}" 的归纳文件，请先完成归纳'})
    raw_full_text = _build_full_skill_generation_context(summary_files)
    raw_total_chars = len(raw_full_text)
    raw_estimated_tokens = _estimate_tokens_from_text(raw_full_text)
    model_name = data.get('modelname', '')
    context_limit = get_model_context_limit(model_name)
    context_limit_tokens = calculate_compression_threshold(context_limit)
    target_budget_tokens = context_limit_tokens
    
    print(f"Model: {model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}")
    print(f"Compression mode: {compression_mode}, Force no compression: {force_no_compression}, Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}")

    if not force_no_compression and raw_estimated_tokens > context_limit_tokens:
        if compression_mode == 'llm':
            print(f"Using LLM compression")
            llm_interaction = get_llm_client()
            summaries_text = _compress_with_llm(summary_files, llm_interaction, target_budget_tokens, checkpoint_id=checkpoint_id)
            context_mode = "llm_compressed"
        else:
            print(f"Using original compression")
            target_budget_chars = target_budget_tokens * 2
            summaries_text = _build_prioritized_skill_generation_context(
                summary_files,
                target_total_chars=target_budget_chars
            )
            context_mode = "compressed"
    else:
        summaries_text = raw_full_text
        if force_no_compression and raw_estimated_tokens > context_limit_tokens:
            context_mode = "full_forced"
            print(f"Force no compression enabled, using full context despite exceeding limit")
        else:
            context_mode = "full"

    if not summaries_text:
        return jsonify({'success': False, 'message': f'未能读取角色 "{role_name}" 的归纳内容'})
    compressed_chars = len(summaries_text)
    estimated_tokens = _estimate_tokens_from_text(summaries_text)
    compression_ratio = (compressed_chars / raw_total_chars) if raw_total_chars else 0
    strategy_name = {
        'full': 'full_context',
        'full_forced': 'full_context_no_compression',
        'compressed': 'head_tail_weighted_1_2_then_key_sections',
        'llm_compressed': 'llm_deduplication'
    }.get(context_mode, 'unknown')
    
    print(
        f"role={role_name} files={len(summary_files)} mode={context_mode} "
        f"raw_chars={raw_total_chars} raw_estimated_tokens={raw_estimated_tokens} "
        f"final_chars={compressed_chars} final_estimated_tokens={estimated_tokens} "
        f"compression_ratio={compression_ratio:.2%} "
        f"strategy={strategy_name}"
    )
    llm_interaction = get_llm_client()
    
    if not resume_checkpoint_id:
        messages, tools = llm_interaction.generate_skills_folder_init(summaries_text, role_name, output_language, vndb_data)
        ckpt_manager.update_progress(checkpoint_id, total_steps=20, current_phase='tool_call_loop')
    else:
        _, tools = llm_interaction.generate_skills_folder_init(summaries_text, role_name, output_language, vndb_data)

    max_iterations = 20
    while iteration < max_iterations:
        iteration += 1
        ckpt_manager.save_llm_state(
            checkpoint_id, messages=messages,
            iteration_count=iteration, all_results=all_results
        )
        response = llm_interaction.send_message(messages, tools, use_counter=False)
        if not response:
            ckpt_manager.save_llm_state(
                checkpoint_id, messages=messages,
                last_response=None, iteration_count=iteration, all_results=all_results
            )
            ckpt_manager.mark_failed(checkpoint_id, 'LLM交互失败')
            return jsonify({
                'success': False, 'message': 'LLM交互失败',
                'checkpoint_id': checkpoint_id, 'can_resume': True
            })
        tool_calls = llm_interaction.get_tool_response(response)
        if not tool_calls:
            break
        assistant_message = {
            "role": "assistant",
            "content": response.choices[0].message.content if response.choices[0].message.content else "",
            "tool_calls": [tc if isinstance(tc, dict) else {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            } for tc in tool_calls]
        }
        messages.append(assistant_message)
        for tool_call in tool_calls:
            result = ToolHandler.handle_tool_call(tool_call)
            all_results.append(result)
            tool_response = {
                "role": "tool",
                "tool_call_id": tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                "content": json.dumps({"success": True, "result": result})
            }
            messages.append(tool_response)
        ckpt_manager.save_llm_state(
            checkpoint_id, messages=messages,
            last_response=response, iteration_count=iteration, all_results=all_results
        )
    try:
        script_dir = get_base_dir()
        main_skill_dir = os.path.join(script_dir, f"{role_name}-skill-main")
        code_skill_dir = os.path.join(script_dir, f"{role_name}-skill-code")
        
        if vndb_data:
            skill_md_path = os.path.join(main_skill_dir, "SKILL.md")
            if os.path.exists(skill_md_path):
                try:
                    with open(skill_md_path, 'r', encoding='utf-8') as f:
                        skill_content = f.read()
                    
                    vndb_section = "\n\n---\n\n## VNDB Character Information\n\n"
                    if vndb_data.get('name'):
                        vndb_section += f"- **Name**: {vndb_data['name']}\n"
                    if vndb_data.get('original_name'):
                        vndb_section += f"- **Original Name**: {vndb_data['original_name']}\n"
                    if vndb_data.get('aliases'):
                        vndb_section += f"- **Aliases**: {', '.join(vndb_data['aliases'])}\n"
                    if vndb_data.get('description'):
                        vndb_section += f"- **Description**: {vndb_data['description']}\n"
                    if vndb_data.get('age'):
                        vndb_section += f"- **Age**: {vndb_data['age']}\n"
                    if vndb_data.get('birthday'):
                        vndb_section += f"- **Birthday**: {vndb_data['birthday']}\n"
                    if vndb_data.get('blood_type'):
                        vndb_section += f"- **Blood Type**: {vndb_data['blood_type']}\n"
                    if vndb_data.get('height'):
                        vndb_section += f"- **Height**: {vndb_data['height']}cm\n"
                    if vndb_data.get('weight'):
                        vndb_section += f"- **Weight**: {vndb_data['weight']}kg\n"
                    if vndb_data.get('bust') and vndb_data.get('waist') and vndb_data.get('hips'):
                        vndb_section += f"- **Measurements**: {vndb_data['bust']}-{vndb_data['waist']}-{vndb_data['hips']}cm\n"
                    if vndb_data.get('traits'):
                        vndb_section += f"- **Traits**: {', '.join(vndb_data['traits'])}\n"
                    if vndb_data.get('vns'):
                        games = vndb_data['vns'][:3]
                        vndb_section += f"- **Visual Novels**: {', '.join(games)}\n"
                    
                    skill_content += vndb_section
                    
                    with open(skill_md_path, 'w', encoding='utf-8') as f:
                        f.write(skill_content)
                    
                    all_results.append(f"Added VNDB info to SKILL.md")
                except Exception as e:
                    all_results.append(f"Warning: Failed to add VNDB info to SKILL.md: {e}")
        
        if os.path.exists(main_skill_dir):
            if os.path.exists(code_skill_dir):
                import shutil
                shutil.rmtree(code_skill_dir)
            import shutil
            shutil.copytree(main_skill_dir, code_skill_dir)
            limit_file = os.path.join(code_skill_dir, "limit.md")
            if os.path.exists(limit_file):
                os.remove(limit_file)
            all_results.append(f"Created {role_name}-skill-code (without limit.md)")
    except Exception as e:
        all_results.append(f"Warning: Failed to create -code version: {e}")
    ckpt_manager.mark_completed(checkpoint_id)
    return jsonify({
        'success': True,
        'message': f'技能文件夹生成完成，共执行 {len(all_results)} 次文件写入',
        'results': all_results,
        'checkpoint_id': checkpoint_id
    })

def download_vndb_image(image_url, output_path):
    if not image_url:
        return False
    try:
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Failed to download image: {e}")
    return False


def embed_json_in_png(json_data, png_path, output_png_path):
    try:
        with open(png_path, 'rb') as f:
            png_data = f.read()

        if png_data[:8] != b'\x89PNG\r\n\x1a\n':
            print("Invalid PNG signature")
            return False

        json_str = json.dumps(json_data, ensure_ascii=False, separators=(',', ':'))
        json_bytes = json_str.encode('utf-8')
        json_base64 = base64.b64encode(json_bytes).decode('ascii')
        text_data = b'chara\x00' + json_base64.encode('ascii')

        crc = zlib.crc32(b'tEXt' + text_data) & 0xffffffff

        tex_chunk = (
            len(text_data).to_bytes(4, 'big') +
            b'tEXt' +
            text_data +
            crc.to_bytes(4, 'big')
        )

        chunks = []
        pos = 8  

        while pos < len(png_data):
            if pos + 8 > len(png_data):
                break

            length = int.from_bytes(png_data[pos:pos+4], 'big')
            chunk_type = png_data[pos+4:pos+8]

            if pos + 12 + length > len(png_data):
                break

            chunk_data = png_data[pos:pos+12+length]
            chunks.append((chunk_type, chunk_data))

            pos += 12 + length

        new_png = png_data[:8]  
        tex_inserted = False

        for i, (chunk_type, chunk_data) in enumerate(chunks):
            if chunk_type == b'IDAT' and not tex_inserted:
                new_png += tex_chunk
                tex_inserted = True

            new_png += chunk_data

        if not tex_inserted:
            new_png += tex_chunk

        with open(output_png_path, 'wb') as f:
            f.write(new_png)

        print(f"Successfully embedded JSON into PNG: {output_png_path}")
        return True

    except Exception as e:
        print(f"Failed to embed JSON in PNG: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_character_card(data):
    role_name = data.get('role_name', '')
    creator = data.get('creator', '')
    vndb_data_raw = data.get('vndb_data')
    vndb_data = clean_vndb_data(vndb_data_raw)
    output_language = data.get('output_language', '')
    compression_mode = data.get('compression_mode', 'original')
    force_no_compression = data.get('force_no_compression', False)
    resume_checkpoint_id = data.get('resume_checkpoint_id')

    if resume_checkpoint_id:
        ckpt = ckpt_manager.load_checkpoint(resume_checkpoint_id)
        if not ckpt:
            return jsonify({'success': False, 'message': f'未找到Checkpoint: {resume_checkpoint_id}'})
        if ckpt['status'] == 'completed':
            return jsonify({'success': False, 'message': '该任务已完成，无需恢复'})
        
        role_name = ckpt['input_params'].get('role_name', role_name)
        creator = ckpt['input_params'].get('creator', creator)
        vndb_data = ckpt['input_params'].get('vndb_data', vndb_data)
        vndb_data_raw = ckpt['input_params'].get('vndb_data_raw', vndb_data_raw)
        output_language = ckpt['input_params'].get('output_language', output_language)
        compression_mode = ckpt['input_params'].get('compression_mode', compression_mode)
        force_no_compression = ckpt['input_params'].get('force_no_compression', force_no_compression)
        checkpoint_id = resume_checkpoint_id
        
        llm_state = ckpt_manager.load_llm_state(checkpoint_id)
        fields_data = llm_state.get('fields_data', {})
        messages = llm_state.get('messages', [])
        iteration_count = llm_state.get('iteration_count', 0)
        
        print(f"Resuming generate_chara_card: iteration {iteration_count}, fields: {list(fields_data.keys())}")
    else:
        checkpoint_id = ckpt_manager.create_checkpoint(
            task_type='generate_chara_card',
            input_params={
                'role_name': role_name,
                'creator': creator,
                'vndb_data': vndb_data,
                'vndb_data_raw': vndb_data_raw,
                'output_language': output_language,
                'compression_mode': compression_mode,
                'force_no_compression': force_no_compression
            }
        )
        fields_data = {}
        messages = []
        iteration_count = 0

    script_dir = get_base_dir()

    analysis_file = None
    for root, dirs, files in os.walk(script_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                summaries_dir = os.path.join(root, dir_name)
                summary_path = os.path.join(summaries_dir, f"{role_name}_analysis_summary.json")
                if os.path.exists(summary_path):
                    analysis_file = summary_path
                    break
        if analysis_file:
            break

    if not analysis_file:
        return jsonify({'success': False, 'message': f'未找到角色 "{role_name}" 的分析文件，请先完成归纳'})

    try:
        with open(analysis_file, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取分析文件失败: {str(e)}'})

    all_character_analyses = analysis_data.get('character_analyses', [])
    all_lorebook_entries = analysis_data.get('lorebook_entries', [])

    if not all_character_analyses:
        return jsonify({'success': False, 'message': '分析数据为空'})

    analyses_text = json.dumps(all_character_analyses, ensure_ascii=False)
    raw_estimated_tokens = _estimate_tokens_from_text(analyses_text)
    model_name = data.get('modelname', '')
    context_limit = get_model_context_limit(model_name)
    context_limit_tokens = calculate_compression_threshold(context_limit)
    target_budget_tokens = context_limit_tokens
    
    print(f"Model: {model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}")
    print(f"Compression mode: {compression_mode}, Force no compression: {force_no_compression}, Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}")

    if not force_no_compression and raw_estimated_tokens > context_limit_tokens:
        if compression_mode == 'llm':
            print(f"Using LLM compression for analyses")
            llm_interaction = get_llm_client()
            compressed_analyses = _compress_analyses_with_llm(all_character_analyses, llm_interaction, target_budget_tokens, checkpoint_id=checkpoint_id)
            all_character_analyses = compressed_analyses
            context_mode = "llm_compressed"
        else:
            print(f"Using original compression")
            target_count = max(1, len(all_character_analyses) * target_budget_tokens // raw_estimated_tokens)
            all_character_analyses = all_character_analyses[:target_count]
            context_mode = "compressed"
        
        compressed_text = json.dumps(all_character_analyses, ensure_ascii=False)
        compressed_tokens = _estimate_tokens_from_text(compressed_text)
        print(f"Compressed: {raw_estimated_tokens} -> {compressed_tokens} tokens ({compressed_tokens/raw_estimated_tokens*100:.1f}%)")
    else:
        if force_no_compression and raw_estimated_tokens > context_limit_tokens:
            context_mode = "full_forced"
            print(f"Force no compression enabled, using full context despite exceeding limit")
        else:
            context_mode = "full"
        print(f"No compression needed ({raw_estimated_tokens} <= {context_limit_tokens})")

    output_dir = os.path.join(script_dir, f"{role_name}-character-card")
    os.makedirs(output_dir, exist_ok=True)
    json_output_path = os.path.join(output_dir, f"{role_name}_chara_card.json")

    image_path = None
    if vndb_data_raw and vndb_data_raw.get('image_url'):
        image_ext = os.path.splitext(vndb_data_raw['image_url'])[1] or '.jpg'
        ckpt_temp_dir = ckpt_manager.get_temp_dir(checkpoint_id)
        image_path = os.path.join(ckpt_temp_dir, f"{role_name}_vndb{image_ext}")
        if os.path.exists(image_path):
            print(f"VNDB image already exists: {image_path}")
        elif download_vndb_image(vndb_data_raw['image_url'], image_path):
            print(f"Downloaded VNDB image to: {image_path}")
        else:
            image_path = None

    llm_interaction = get_llm_client()
    result = llm_interaction.generate_character_card_with_tools(
        role_name,
        all_character_analyses,
        all_lorebook_entries,
        json_output_path,
        creator,
        vndb_data,
        output_language,
        checkpoint_id=checkpoint_id,
        ckpt_messages=messages if resume_checkpoint_id else None,
        ckpt_fields_data=fields_data if resume_checkpoint_id else None,
        ckpt_iteration_count=iteration_count if resume_checkpoint_id else None
    )

    if result.get('success'):
        ckpt_manager.mark_completed(checkpoint_id, final_output_path=json_output_path)
        try:
            with open(json_output_path, 'r', encoding='utf-8') as f:
                chara_card_json = json.load(f)
        except Exception as e:
            return jsonify({
                'success': True,
                'message': f'角色卡生成完成 (JSON): {json_output_path}',
                'output_path': json_output_path,
                'fields_written': result.get('fields_written', []),
                'image_path': image_path,
                'warning': f'无法读取JSON用于PNG嵌入: {str(e)}',
                'checkpoint_id': checkpoint_id
            })

        png_output_path = None
        conversion_error = None
        if image_path and os.path.exists(image_path):
            png_output_path = os.path.join(output_dir, f"{role_name}_chara_card.png")

            if image_path.lower().endswith('.png'):
                if embed_json_in_png(chara_card_json, image_path, png_output_path):
                    print(f"Created PNG character card: {png_output_path}")
                else:
                    png_output_path = None
                    conversion_error = "Failed to embed JSON in PNG"
            else:
                try:
                    from PIL import Image
                    img = Image.open(image_path)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        if img.mode in ('RGBA', 'LA'):
                            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                            img = background
                    else:
                        img = img.convert('RGB')
                    temp_png = os.path.join(ckpt_manager.get_temp_dir(checkpoint_id), f"{role_name}_temp.png")
                    img.save(temp_png, 'PNG', optimize=True)
                    print(f"Converted image to PNG: {temp_png}")
                    if embed_json_in_png(chara_card_json, temp_png, png_output_path):
                        print(f"Created PNG character card with embedded JSON: {png_output_path}")
                    else:
                        png_output_path = None
                        conversion_error = "Failed to embed JSON in converted PNG"
                    if os.path.exists(temp_png):
                        os.remove(temp_png)
                except ImportError:
                    conversion_error = "PIL (Pillow) not installed. Run: pip install Pillow"
                    print(conversion_error)
                    png_output_path = None
                except Exception as e:
                    conversion_error = f"Image conversion failed: {str(e)}"
                    print(conversion_error)
                    png_output_path = None

            if image_path and os.path.exists(image_path) and not checkpoint_id:
                try:
                    os.remove(image_path)
                    print(f"Cleaned up VNDB image: {image_path}")
                    image_path = None  
                except Exception as e:
                    print(f"Failed to clean up VNDB image: {e}")

        response_data = {
            'success': True,
            'message': f'角色卡生成完成: {json_output_path}',
            'output_path': json_output_path,
            'fields_written': result.get('fields_written', []),
            'result': result.get('result', ''),
            'checkpoint_id': checkpoint_id
        }

        if image_path:
            response_data['image_path'] = image_path
        if png_output_path:
            response_data['png_path'] = png_output_path
        if conversion_error:
            response_data['conversion_error'] = conversion_error

        return jsonify(response_data)
    else:
        if result.get('can_resume'):
            ckpt_manager.mark_failed(checkpoint_id, result.get('message', '生成失败'))
            return jsonify({
                'success': False,
                'message': result.get('message', '生成失败'),
                'checkpoint_id': checkpoint_id,
                'can_resume': True
            })
        return jsonify({
            'success': False,
            'message': result.get('message', '生成失败')
        })

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
    ckpt = ckpt_manager.load_checkpoint(checkpoint_id)
    if not ckpt:
        return jsonify({'success': False, 'message': f'未找到Checkpoint: {checkpoint_id}'})
    if ckpt['status'] == 'completed':
        return jsonify({'success': False, 'message': '该任务已完成，无需恢复'})
    
    task_type = ckpt['task_type']
    input_params = ckpt.get('input_params', {})
    input_params['resume_checkpoint_id'] = checkpoint_id
    
    extra_params = request.json or {}
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
    data = request.json
    vndb_id = data.get('vndb_id', '').strip()

    if not vndb_id:
        return jsonify({'success': False, 'message': '未提供VNDB ID'})

    char_id = vndb_id
    if vndb_id.lower().startswith('c'):
        char_id = vndb_id[1:]

    if not char_id.isdigit():
        return jsonify({'success': False, 'message': '无效的VNDB ID格式，应为 c+数字 或纯数字'})

    try:
        api_request = {
            'filters': ['id', '=', f'c{char_id}'],
            'fields': 'id,name,original,aliases,description,age,birthday,blood_type,height,weight,bust,waist,hips,image.url,traits.name,vns.title,sex'
        }

        response = requests.post(
            'https://api.vndb.org/kana/character',
            json=api_request,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])

            if results and len(results) > 0:
                character = results[0]

                birthday = character.get('birthday', [])
                birthday_str = ""
                if birthday and len(birthday) >= 2:
                    birthday_str = f"{birthday[0]}/{birthday[1]}"  
                traits = character.get('traits', [])
                trait_names = [t.get('name', '') for t in traits if t.get('name', '') not in R18_TRAITS]

                vns = character.get('vns', [])
                vn_list = [v.get('title', '') for v in vns if v.get('title', '')]

                return jsonify({
                    'success': True,
                    'data': {
                        'vndb_id': vndb_id,
                        'name': character.get('name', ''),
                        'original_name': character.get('original', ''),
                        'aliases': character.get('aliases', []),
                        'description': character.get('description', ''),
                        'age': character.get('age', ''),
                        'birthday': birthday_str,
                        'blood_type': character.get('blood_type', ''),
                        'height': character.get('height', ''),
                        'weight': character.get('weight', ''),
                        'bust': character.get('bust', ''),
                        'waist': character.get('waist', ''),
                        'hips': character.get('hips', ''),
                        'image_url': character.get('image', {}).get('url', ''),
                        'traits': trait_names,
                        'vns': vn_list
                    }
                })
            else:
                return jsonify({'success': False, 'message': '未找到该角色'})
        else:
            return jsonify({'success': False, 'message': f'VNDB API请求失败: HTTP {response.status_code}'})

    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': 'VNDB API请求超时'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取VNDB信息失败: {str(e)}'})

if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
