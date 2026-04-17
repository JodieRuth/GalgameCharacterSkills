import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils.llm_interaction import LLMInteraction
from utils.tool_handler import ToolHandler
from services.checkpoint_utils import load_resumable_checkpoint
from services.request_config import build_llm_config


def _process_single_slice(args, ckpt_manager):
    slice_index, slice_content, role_name, instruction, output_file_path, config, output_language, mode, vndb_data, checkpoint_id = args
    llm_client = LLMInteraction()
    if config.get('baseurl') or config.get('modelname') or config.get('apikey'):
        llm_client.set_config(config.get('baseurl'), config.get('modelname'), config.get('apikey'), max_retries=config.get('max_retries'))

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


def run_summarize_task(data, file_processor, ckpt_manager, build_llm_client, clean_vndb_data):
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
        return {'success': False, 'message': '请输入角色名称'}

    config = build_llm_config(data)
    output_language = data.get('output_language', '')
    vndb_data = clean_vndb_data(data.get('vndb_data'))
    slice_size_k = data.get('slice_size_k', 50)

    if resume_checkpoint_id:
        ckpt, error = load_resumable_checkpoint(ckpt_manager, resume_checkpoint_id)
        if error:
            return error

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
            return {'success': False, 'message': '请先选择文件'}

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
        return {'success': False, 'message': '请先选择文件'}

    _ = build_llm_client(config)
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
        future_to_task = {executor.submit(_process_single_slice, task, ckpt_manager): task for task in tasks}

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
        return {
            'success': False,
            'message': f'归纳失败，{len(errors)} 个切片失败',
            'slice_count': len(current_slices),
            'errors': errors,
            'results': all_results,
            'checkpoint_id': checkpoint_id,
            'can_resume': True
        }

    if errors:
        ckpt_manager.mark_failed(checkpoint_id, f'{len(errors)} 个切片失败，可恢复继续处理')
        return {
            'success': True,
            'message': f'归纳部分完成，{len(errors)} 个切片失败，可通过任务列表继续',
            'slice_count': len(current_slices),
            'errors': errors,
            'results': all_results,
            'checkpoint_id': checkpoint_id,
            'can_resume': True
        }

    ckpt_manager.mark_completed(checkpoint_id)
    return {
        'success': True,
        'message': '归纳完成',
        'slice_count': len(current_slices),
        'results': all_results,
        'checkpoint_id': checkpoint_id
    }
