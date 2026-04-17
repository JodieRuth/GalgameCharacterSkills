import json
import os
import time
from concurrent.futures import as_completed

from ..utils.checkpoint_utils import load_resumable_checkpoint
from ..utils.request_config import build_llm_config
from ..utils.input_normalization import extract_file_paths
from ..domain import SummarizeRequest, ok_result, fail_result


def _process_single_slice(args, ckpt_manager, llm_gateway, tool_gateway, storage_gateway):
    slice_index, slice_content, role_name, instruction, output_file_path, config, output_language, mode, vndb_data, checkpoint_id = args
    llm_client = llm_gateway.create_client(config)

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
                    if not storage_gateway.exists(output_file_path):
                        return result
                    parsed = storage_gateway.read_json(output_file_path)
                    result['character_analysis'] = parsed.get('character_analysis', {})
                    result['lorebook_entries'] = parsed.get('lorebook_entries', [])
                except Exception:
                    pass
            else:
                try:
                    if not storage_gateway.exists(output_file_path):
                        return result
                    content = storage_gateway.read_text(output_file_path)
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
                    tool_result = tool_gateway.handle_tool_call(tool_call)
                    result['tool_results'].append(tool_result)
                result['success'] = True
                result['summary'] = f"Slice {slice_index + 1} saved to {output_file_path}"

                try:
                    parsed = storage_gateway.read_json(output_file_path)
                    result['character_analysis'] = parsed.get('character_analysis', {})
                    result['lorebook_entries'] = parsed.get('lorebook_entries', [])
                except Exception as e:
                    result['tool_results'].append(f"Warning: Failed to read saved file: {e}")

            elif hasattr(choice, 'message') and choice.message.content:
                content = choice.message.content
                parsed = tool_gateway.parse_llm_json_response(content)
                if parsed:
                    result['character_analysis'] = parsed.get('character_analysis', {})
                    result['lorebook_entries'] = parsed.get('lorebook_entries', [])
                    result['success'] = True
                    result['summary'] = f"Slice {slice_index + 1} analyzed successfully"
                    storage_gateway.write_json(output_file_path, parsed, ensure_ascii=False, indent=2)
        else:
            if hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    tool_result = tool_gateway.handle_tool_call(tool_call)
                    result['tool_results'].append(tool_result)
                result['success'] = True
                result['summary'] = f"Slice {slice_index + 1} saved to {output_file_path}"
            else:
                result['success'] = True
                result['summary'] = choice.message.content

    if result['success'] and checkpoint_id:
        try:
            if mode == 'chara_card':
                ckpt_content = storage_gateway.read_text(output_file_path)
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
            ckpt_manager.mark_slice_completed(checkpoint_id, slice_index)
        except Exception as e:
            print(f"Failed to save slice {slice_index} result: {e}")

    return result


def run_summarize_task(data, runtime):
    request_data = SummarizeRequest.from_payload(data, runtime.clean_vndb_data, extract_file_paths)

    if not request_data.role_name:
        return fail_result('请输入角色名称')

    config = build_llm_config(data)
    if request_data.resume_checkpoint_id:
        ckpt_result = load_resumable_checkpoint(runtime.checkpoint_gateway, request_data.resume_checkpoint_id)
        if not ckpt_result.get('success'):
            return ckpt_result
        ckpt = ckpt_result['checkpoint']

        request_data.apply_checkpoint(ckpt['input_params'])
        checkpoint_id = request_data.resume_checkpoint_id

        completed_indices = set(ckpt['progress'].get('completed_items', []))
        print(f"Resuming summarize: {len(completed_indices)}/{ckpt['progress'].get('total_steps', '?')} slices already done")
    else:
        if not request_data.file_paths:
            return fail_result('请先选择文件')

        checkpoint_id = runtime.checkpoint_gateway.create_checkpoint(
            task_type='summarize',
            input_params=request_data.to_checkpoint_input()
        )

    if not request_data.file_paths:
        return fail_result('请先选择文件')

    current_slices = runtime.file_processor.slice_multiple_files(request_data.file_paths, request_data.slice_size_k)
    runtime.llm_gateway.set_total_requests(len(current_slices))

    summaries = []
    errors = []
    all_results = []
    all_character_analyses = []
    all_lorebook_entries = []

    if len(request_data.file_paths) == 1:
        file_name = os.path.basename(request_data.file_paths[0])
        name, ext = os.path.splitext(file_name)
        summary_dir = os.path.join(os.path.dirname(request_data.file_paths[0]), f"{name}_summaries")
    else:
        first_dir = os.path.dirname(request_data.file_paths[0])
        name = os.path.basename(request_data.file_paths[0])
        name = os.path.splitext(name)[0]
        summary_dir = os.path.join(first_dir, f"{name}_merged_summaries")
    runtime.storage_gateway.makedirs(summary_dir, exist_ok=True)

    if not request_data.resume_checkpoint_id:
        runtime.checkpoint_gateway.update_progress(
            checkpoint_id,
            total_steps=len(current_slices),
            pending_items=list(range(len(current_slices)))
        )

    tasks = []
    for i, slice_content in enumerate(current_slices):
        if request_data.mode == 'chara_card':
            output_file_path = os.path.join(summary_dir, f"slice_{i+1:03d}_{request_data.role_name}.json")
        else:
            output_file_path = os.path.join(summary_dir, f"slice_{i+1:03d}_{request_data.role_name}.md")
        tasks.append((
            i,
            slice_content,
            request_data.role_name,
            request_data.instruction,
            output_file_path,
            config,
            request_data.output_language,
            request_data.mode,
            request_data.vndb_data,
            checkpoint_id
        ))

    with runtime.executor_gateway.create(max_workers=request_data.concurrency) as executor:
        future_to_task = {
            executor.submit(
                _process_single_slice,
                task,
                runtime.checkpoint_gateway,
                runtime.llm_gateway,
                runtime.tool_gateway,
                runtime.storage_gateway
            ): task
            for task in tasks
        }

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

    if request_data.mode == 'chara_card':
        analysis_summary_path = os.path.join(summary_dir, f"{request_data.role_name}_analysis_summary.json")
        runtime.storage_gateway.write_json(
            analysis_summary_path,
            {
                'character_analyses': all_character_analyses,
                'lorebook_entries': all_lorebook_entries
            },
            ensure_ascii=False,
            indent=2
        )

    if errors and len(summaries) == 0:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, f'{len(errors)} 个切片全部失败')
        return fail_result(
            f'归纳失败，{len(errors)} 个切片失败',
            slice_count=len(current_slices),
            errors=errors,
            results=all_results,
            checkpoint_id=checkpoint_id,
            can_resume=True
        )

    if errors:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, f'{len(errors)} 个切片失败，可恢复继续处理')
        return ok_result(
            message=f'归纳部分完成，{len(errors)} 个切片失败，可通过任务列表继续',
            slice_count=len(current_slices),
            errors=errors,
            results=all_results,
            checkpoint_id=checkpoint_id,
            can_resume=True
        )

    runtime.checkpoint_gateway.mark_completed(checkpoint_id)
    return ok_result(
        message='归纳完成',
        slice_count=len(current_slices),
        results=all_results,
        checkpoint_id=checkpoint_id
    )
