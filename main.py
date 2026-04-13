import os
import sys
import webbrowser
import threading
import time
import json
import requests
import zlib
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from utils.llm_interaction import LLMInteraction
from utils.file_processor import FileProcessor
from utils.tool_handler import ToolHandler


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
current_slices = []
summaries = []

class NoRequestFilter:
    def filter(self, record):
        return not (record.getMessage().startswith('127.0.0.1') and 'HTTP' in record.getMessage())

import logging
log = logging.getLogger('werkzeug')
log.addFilter(NoRequestFilter())

def open_browser():
    time.sleep(1.5)
    webbrowser.open('http://127.0.0.1:5000')

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
    if not file_path:
        return jsonify({'success': False, 'message': '未提供文件路径'})
    try:
        token_count = file_processor.calculate_tokens(file_path)
        slice_count = file_processor.calculate_slices(token_count)
        return jsonify({
            'success': True,
            'token_count': token_count,
            'slice_count': slice_count,
            'formatted_tokens': f"{token_count:,}"
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/slice', methods=['POST'])
def slice_file():
    data = request.json
    selected_file = data.get('file_path', '')
    if not selected_file:
        return jsonify({'success': False, 'message': '请先选择文件'})
    try:
        global current_slices
        current_slices = file_processor.slice_file(selected_file)
        return jsonify({
            'success': True,
            'message': f'文件已切片，共 {len(current_slices)} 个切片',
            'slice_count': len(current_slices)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'切片失败: {str(e)}'
        })

def process_single_slice(args):
    slice_index, slice_content, role_name, instruction, output_file_path, config, output_language, mode, vndb_data = args
    llm_client = LLMInteraction()
    if config.get('baseurl') or config.get('modelname') or config.get('apikey'):
        llm_client.set_config(config.get('baseurl'), config.get('modelname'), config.get('apikey'))

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
        'lorebook_entries': []
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
    
    return result


@app.route('/api/summarize', methods=['POST'])
def summarize():
    global current_slices, summaries
    data = request.json
    role_name = data.get('role_name', '')
    instruction = data.get('instruction', '')
    selected_file = data.get('file_path', '')
    concurrency = data.get('concurrency', 1)
    mode = data.get('mode', 'skills')
    
    if not role_name:
        return jsonify({'success': False, 'message': '请输入角色名称'})
    if not selected_file:
        return jsonify({'success': False, 'message': '请先选择文件'})
    
    llm_interaction = get_llm_client()
    current_slices = file_processor.slice_file(selected_file)
    LLMInteraction.set_total_requests(len(current_slices))
    
    summaries = []
    errors = []
    all_results = []
    all_character_analyses = []
    all_lorebook_entries = []
    
    file_name = os.path.basename(selected_file)
    name, ext = os.path.splitext(file_name)
    summary_dir = os.path.join(os.path.dirname(selected_file), f"{name}_summaries")
    os.makedirs(summary_dir, exist_ok=True)
    
    config = {
        'baseurl': data.get('baseurl', ''),
        'modelname': data.get('modelname', ''),
        'apikey': data.get('apikey', '')
    }

    output_language = data.get('output_language', '')
    vndb_data = clean_vndb_data(data.get('vndb_data'))

    tasks = []
    for i, slice_content in enumerate(current_slices):
        if mode == 'chara_card':
            output_file_path = os.path.join(summary_dir, f"slice_{i+1:03d}_{role_name}.json")
        else:
            output_file_path = os.path.join(summary_dir, f"slice_{i+1:03d}_{role_name}.md")
        tasks.append((i, slice_content, role_name, instruction, output_file_path, config, output_language, mode, vndb_data))
    
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
    
    if errors:
        return jsonify({
            'success': len(summaries) > 0,
            'message': f'归纳完成，{len(errors)} 个切片失败',
            'slice_count': len(current_slices),
            'errors': errors,
            'results': all_results
        })
    
    return jsonify({
        'success': True,
        'message': '归纳完成',
        'slice_count': len(current_slices),
        'results': all_results
    })

@app.route('/api/skills', methods=['POST'])
def generate_skills():
    data = request.json
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
    all_summaries = []
    for file_path in summary_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                all_summaries.append(f"=== {os.path.basename(file_path)} ===\n{content}")
        except Exception as e:
            pass
    summaries_text = "\n\n".join(all_summaries)
    llm_interaction = get_llm_client()
    messages, tools = llm_interaction.generate_skills_folder_init(summaries_text, role_name, output_language, vndb_data)
    all_results = []
    max_iterations = 20
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        response = llm_interaction.send_message(messages, tools, use_counter=False)
        if not response:
            return jsonify({'success': False, 'message': 'LLM交互失败'})
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
            import json
            tool_response = {
                "role": "tool",
                "tool_call_id": tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id'),
                "content": json.dumps({"success": True, "result": result})
            }
            messages.append(tool_response)
    try:
        script_dir = get_base_dir()
        main_skill_dir = os.path.join(script_dir, f"{role_name}-skill-main")
        code_skill_dir = os.path.join(script_dir, f"{role_name}-skill-code")
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
    return jsonify({
        'success': True,
        'message': f'技能文件夹生成完成，共执行 {len(all_results)} 次文件写入',
        'results': all_results
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

    output_dir = os.path.join(script_dir, f"{role_name}-character-card")
    os.makedirs(output_dir, exist_ok=True)
    json_output_path = os.path.join(output_dir, f"{role_name}_chara_card.json")

    image_path = None
    if vndb_data_raw and vndb_data_raw.get('image_url'):
        image_ext = os.path.splitext(vndb_data_raw['image_url'])[1] or '.jpg'
        image_path = os.path.join(script_dir, f"{role_name}_vndb{image_ext}")
        if download_vndb_image(vndb_data_raw['image_url'], image_path):
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
        output_language
    )

    if result.get('success'):
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
                'warning': f'无法读取JSON用于PNG嵌入: {str(e)}'
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
                    temp_png = os.path.join(script_dir, f"{role_name}_temp.png")
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

            if image_path and os.path.exists(image_path):
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
            'result': result.get('result', '')
        }

        if image_path:
            response_data['image_path'] = image_path
        if png_output_path:
            response_data['png_path'] = png_output_path
        if conversion_error:
            response_data['conversion_error'] = conversion_error

        return jsonify(response_data)
    else:
        return jsonify({
            'success': False,
            'message': result.get('message', '生成失败')
        })

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
                r18_traits = {
                    #VNDB中所有的r18标签
                    'Armpit Licking', 'Armpit Sex', 'Ball-cupping', 'Balljob', 'Bellyjob',
                    'Blowbang', 'Double Handjob', 'Footjob on Multiple Penises', 'Group (4+) Blowjob',
                    'Footjob', 'Thigh Sex', 'Hairjob', 'Ear Sex', 'Navel Sex', 'Axillary Intercourse',
                    'Intercrural Sex', 'Mammary Intercourse', 'Paizuri', 'Sumata', 'Boobjob',
                    'Handjob', 'Double Handjob', 'Group (4+) Handjob', 'Nursing Handjob', 'Rimming Handjob',
                    'Triple Handjob', 'Twin Handjob', 'Auto-Boobjob', 'Group (4+) Boobjob', 'Naizuri',
                    'Triple Boobjob', 'Twin Boobjob', 'Frot', 'Shoejob', 'Kneepit Sex',
                    'Single Leg Legjob', 'Twin+ Legjob', 'Legwear Footjob', 'Triple Footjob', 'Twin Footjob',
                    'Bodysponge', 'Intercrural Sex', 'Tailjob', 'Tribadism', 'Tribadism on Penis',
                    'Twin Bellyjob', 'Adult Breast Sucking', 'Docking', 'Nipple Teasing',
                    'Feet Licking', 'Foreskin Play', 'Pantyjob', 'Pegjob', 'Petting With Object',
                    'Amazon Position', 'Butterfly Position', 'Cowgirl', 'Doggy Style',
                    'Missionary', 'Reverse Cowgirl', 'Spoons', 'Standing Sex', 'Sitting Sex',
                    'Seventh Posture', 'Tominagi', 'Reverse Piledriver', 'Piledriver',
                    'Reverse Missionary', 'Reverse Spitroast', 'Spit-roast', 'Quickie Fix',
                    'Group Sex', 'Group Sex of One Male and Several Females',
                    'Blowjob', 'Double Blowjob', 'Twin Blowjob', 'Deepthroat',
                    'Group Sex Involving Gender Non-conforming Individuals',
                    'Group Sex of Multiple Females and Males', 'Group Sex of One Female and Several Males',
                    'Group Sex of One Male and Several Females', 'Group Sex of Several Females',
                    'Group Sex of Several Males', 'Blowbang (One Mouth Multiple Penises)',
                    'Group Sex with Clones', 'Twin Balls Sucking', 'Twin Blowjob', 'Twin Bodyjob',
                    'Twin Buttjob', 'Twin Footjob', 'Twin Handjob',
                    'Blowjob', 'Double Blowjob', 'Twin Blowjob', 'Deepthroat', 'Triple Blowjob',
                    'Balls Sucking', 'Sensual Biting',
                    'Anal Sex', 'Anal Fingering', 'Anal Fisting', 'Anilingus',
                    'Anal Object Insertion', 'Anal Liquid Expulsion', 'Ass to Mouth',
                    'Prostate Massage', 'Pegging', 'Anal Object Expulsion',
                    'Cunnilingus', 'Fellatio', 'Sixty-nine', 'Handjob', 'Fingering',
                    'Double Fingering', 'Mouth Fingering', 'Vaginal Fingering',
                    'Female Ejaculation', 'Foot Insertion', 'Live Sex Chat',
                    'Masturbation', 'Anal Masturbation', 'Discreet Masturbation',
                    'Masturbation in front of an Audience', 'Masturbation with Object',
                    'Mutual Masturbation', 'Discreet Masturbation',
                    'Humping', 'Masturbation with Water', 'Masturbation in front of the Protagonist',
                    'Vaginal Masturbation', 'Penile Masturbation',
                    'Rape', 'Reverse Rape', 'Gang Rape', 'Monster Rape', 'Sex with Slimes',
                    'Sex with Tentacles', 'Tentacle Rape', 'Molesting', 'Sexual Harassment',
                    'Sexual Child Abuse', 'Non-consensual Erotic Humiliation',
                    'Non-consensual Porn Production', 'Rape by Others', 'Defloration by Others',
                    'Avoidable Sex with Monsters', 'Avoidable Sex with Others',
                    'Bondage', 'BDSM', 'Body Writing', 'Bondage Sex', 'Breast Torture',
                    'Cock and Ball Torture', 'Consensual Erotic Humiliation',
                    'Non-consensual Erotic Humiliation', 'Spanking', 'Whipping',
                    'Choking', 'Asphyxiation', 'Nipple Clamps', 'Hot Wax', 'Ice Play',
                    'Electrostimulation', 'Sounding', 'Urethral Insertion', 'Catheter',
                    'Speculum', 'Medical Play', 'Clothespins',
                    'Impact Play', 'Ballbusting', 'Cockslapping', 'Erotic Beating (Consensual)',
                    'Trampling', 'Whipping (BDSM)', 'Duct Tape Bondage', 'Leather Bondage',
                    'Rope Bondage', 'Mouth Gag', 'Open Gag', 'Panty Gag', 'Ballbusting',
                    'Hair Pulling (Sexual)', 'Piercing Torture (BDSM)', 'Tickle Torture',
                    'Wax Play', 'Used Condoms Exposition', 'Condoms (Clothing)',
                    'Human Furniture', 'Naked Dogeza', 'Orgasm Denial', 'Electric Shock (BDSM)',
                    'Anal Beads', 'Ben Wa Balls', 'Butt Plug', 'Chastity Belt',
                    'Cock Ring', 'Dildo', 'Vibrator', 'Sex Doll', 'Object (Sexual)',
                    'Blowjob on Object', 'Masturbation with Object', 'Petting With Object',
                    'Vaginal Object Expulsion', 'Vaginal Egg Laying', 'Anal Egg Laying', 'Urethral Sounding',
                    'Cum Eating', 'Cum Swallowing', 'Cum Bath', 'Cumplay', 'Bukkake',
                    'Gokkun', 'Creampie Eating', 'Snowballing', 'Felching',
                    'Urine', 'Pissing', 'Pissing on Others', 'Pissing on Own Face',
                    'Watersports', 'Golden Shower', 'Scat', 'Coprophagia', 'Dirty Anal',
                    'Scat on Others', 'Anal Vore', 'Unbirthing', 'Urethral Intercourse',
                    'Vomit', 'Spit Drinking', 'Lotion Play', 'Erotic Spitting',
                    'Vomiting on Others', 'Skull fucking',
                    'Facesitting', 'Teabagging', 'Rimming', 'Analingus',
                    'Armpit Licking', 'Armpit Sex', 'Footjob', 'Testicle Sucking',
                    'Nipple Sucking', 'Breast Smothering', 'Autassassinophiliat',
                    'Erotic Beating (Non-Consensual)', 'Killing Sex',
                    'Virgin Sex', 'Defloration', 'Defloration by an Object',
                    'Repeated Defloration', 'Male Virgin', 'Female Virgin',
                    'Virginity', 'Non-Virgin', 'Hymen', 'Cherry Popping',
                    'First Time Sex', 'Deflowering', 'Cherry Boy', 'Cherry Girl',
                    'All the Way Through', 'Dying Sex',
                    'Pregnant Sex', 'Sex while Being Pregnant', 'Lactation',
                    'Sex Involving Menstruation', 'Impregnation', 'Navel Penetration',
                    'Incest', 'Inbreeding', 'Non-blood-related Incest', 'Selfcest',
                    'Twincest', 'Unbeknownst Incest', 'Incest Roleplay',
                    'NTR', 'Netorare', 'Netori', 'Adultery', 'Cheating', 'Affair',
                    'Infidelity', 'Secret Relationship', 'Cuckold', 'Cuckquean',
                    'Hotwife', 'Stag', 'Vixen', 'Wife Swapping', 'Swinging',
                    'Lolicon', 'Shotacon', 'Sex with Children',
                    'Bestiality', 'Zoophilia', 'Consensual Bestiality',
                    'Non-consensual Bestiality', 'Sex with Insects',
                    'Consensual Sex with Insects', 'Non-consensual Sex with Insects',
                    'Necrophilia', 'Cannibalism', 'Guro', 'Ryona', 'Snuff',
                    'Asphyxiation', 'Choking', 'Strangulation Sex', 'Killing Sex',
                    'Blood', 'Gore', 'Vore', 'Amputee',
                    'Mind Break', 'Corruption', 'Moral Degeneration', 'Personality Change',
                    'Brainwashing', 'Hypnosis', 'Mind Control', 'Possession',
                    'Ahegao', 'Peace Sign Ahegao', 'Rolling Eyes', 'Tongue Out',
                    'Drooling', 'Fucked Silly',
                    'Body Swap', 'Gender Swap', 'Transformation', 'Futanari',
                    'Hermaphrodite', 'Newhalf', 'Shemale', 'Trap', 'Reverse Trap',
                    'Crossdressing', 'Transvestism', 'Transgender', 'Transsexual',
                    'Gender Bender', 'Sex Change', 'Feminization', 'Sissification',
                    'Masculinization', 'Bimbofication', 'Slutification',
                    'Sexual Intercourse', 'Sex with Protagonist Only',
                    'Sex with Others Only', 'Sex with Others', 'Sex with Monsters',
                    'Sex with Tentacles', 'Sex with Slimes', 'Sex with Insects',
                    'Interspecies Sex', 'Monster Sex', 'Alien Sex', 'Machine Sex',
                    'Robot Sex', 'Android Sex', 'Cyborg Sex', 'Tentacle Sex',
                    'Outdoor Sex', 'Public Masturbation', 'Sex in a Vehicle',
                    'Sex in Water', 'Bathroom Sex', 'Church Sex', 'Sleep Sex',
                    'Sex in Public Places', 'Sex at School', 'Sex at Work', 'Sex in Library',
                    'Sex on Beach', 'Sex on Roof', 'Sex Under Water', 'Sex in Karaoke Box',
                    'Sex in Photo Booth', 'Sex in the Air', 'Sex on Toilet',
                    'Wake-up Sex', 'Sex in Front of an Audience',
                    'Naked in Front of an Audience', 'Sex in a Wedding Dress',
                    'Quickie Fix', 'One-night Stand', 'Comfort Sex', 'Casual Sex',
                    'Off-screen Sex Only', 'Detached Sex Scenes Only',
                    'Game Over Sex Scenes Only', 'Text-only Sex Scenes Only',
                    'Masturbation in front of an Audience', 'Naked in Front of an Audience',
                    'Sex in Front of an Audience', 'Voyeurism',
                    'Food Play', 'Body Food', 'Food Gokkun', 'Masturbation Involving Food',
                    'Sexual Cosplay', 'Sexual Animal Cosplay', 'Condom Sex',
                    'Sex Wearing Panties On Face', 'Leg Locking During Sex',
                    'Living Clothes Sex', 'French Kiss',
                    'Gaping', 'Anal Gaping', 'Vaginal Gaping', 'Fisting',
                    'Anal Fisting', 'Vaginal Fisting',
                    'Autopenetration', 'Face-farting', 'Knotting', 'Sexting',
                    'Single Hole Multiple Penetration', 'Wormhole Sex',
                    'Sexual Hair Eating', 'Paraphilic Infantilism',
                    'Rough Sex (Consensual)', 'Sexual Sadism', 'Sexual Masochism',
                    'Milking (Sexual)', 'Sweat Licking', 'Mirror Sex',
                    'Sex Involving Smegma', 'Sex with Protagonist Only',
                    'Sex involving Prostitution', 'Drunk Sex', 'Genderbent Sex',
                    'Pornography', 'Consensual Porn Acting', 'Consumption of Porn',
                    'Non-consensual Porn Acting', 'Non-consensual Porn Production',
                    'Porn Acting (volunteer)', 'Consensual Porn Production',
                    'Non-consensual Porn Acting (volunteer)', 'Non-consensual Porn Distribution',
                    'Sexual Roleplay', 'Rape Roleplay',
                    'Sex Acts by Participants\' Gender', 'Lesbian Sex',
                    'Male on Male Sex', 'Sex Involving Gender Non-conforming Individuals',
                    'Vaginal', 'Cunnilingus', 'Vaginal Fingering', 'Vaginal Fisting',
                    'Promiscuous', 'Slut', 'Manwhore', 'Stud', 'Experienced',
                    'Harem', 'Reverse Harem', 'Polyamory', 'Forbidden Love',
                    'Taboo Relationship'
                }
                trait_names = [t.get('name', '') for t in traits if t.get('name', '') not in r18_traits]

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
