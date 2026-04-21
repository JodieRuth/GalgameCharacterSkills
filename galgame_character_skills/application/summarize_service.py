import json
import os
import time
from concurrent.futures import as_completed

from ..utils.checkpoint_utils import load_resumable_checkpoint
from ..utils.request_config import build_llm_config
from ..utils.input_normalization import extract_file_paths
from ..domain import SummarizeRequest, ok_result, fail_result


def _build_checkpoint_slice_content(mode, output_file_path, choice, result, storage_gateway):
    if mode == 'chara_card':
        return storage_gateway.read_text(output_file_path)

    # Keep checkpoint content aligned with the actual markdown file when present.
    try:
        if storage_gateway.exists(output_file_path):
            return storage_gateway.read_text(output_file_path)
    except Exception:
        pass

    if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
        for tool_call in choice.message.tool_calls:
            if hasattr(tool_call, 'function') and tool_call.function.name == 'write_file':
                args_dict = json.loads(tool_call.function.arguments)
                return args_dict.get('content', '')

    return result['summary'] or ''


def _extract_write_file_content(choice):
    if not (hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls') and choice.message.tool_calls):
        return ""
    for tool_call in choice.message.tool_calls:
        if hasattr(tool_call, 'function') and tool_call.function.name == 'write_file':
            try:
                args_dict = json.loads(tool_call.function.arguments)
            except Exception:
                return ""
            return args_dict.get('content', '') or ''
    return ""


def _finalize_skills_slice_result(result, choice, output_file_path, storage_gateway):
    content_from_tool = _extract_write_file_content(choice)
    content = content_from_tool or (result.get('summary') or "")
    if not content.strip():
        result['success'] = False
        result['summary'] = None
        result['tool_results'].append("Empty summary content")
        return

    # If tool call did not write file, persist content from plain-text response.
    if not content_from_tool:
        storage_gateway.write_text(output_file_path, content)
        result['summary'] = content

    # Treat disk write as the source of truth for success in skills mode.
    if not storage_gateway.exists(output_file_path):
        result['success'] = False
        result['summary'] = None
        result['tool_results'].append("Summary file was not saved")


def _persist_slice_checkpoint_if_needed(checkpoint_id, slice_index, mode, output_file_path, choice, result, ckpt_manager, storage_gateway):
    if not (result['success'] and checkpoint_id):
        return

    try:
        ckpt_content = _build_checkpoint_slice_content(
            mode=mode,
            output_file_path=output_file_path,
            choice=choice,
            result=result,
            storage_gateway=storage_gateway,
        )
        ckpt_manager.save_slice_result(checkpoint_id, slice_index, ckpt_content, 'completed')
        ckpt_manager.mark_slice_completed(checkpoint_id, slice_index)
    except Exception as e:
        print(f"Failed to save slice {slice_index} result: {e}")


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
    choice = None

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
            _finalize_skills_slice_result(result, choice, output_file_path, storage_gateway)

    if choice is not None:
        _persist_slice_checkpoint_if_needed(
            checkpoint_id=checkpoint_id,
            slice_index=slice_index,
            mode=mode,
            output_file_path=output_file_path,
            choice=choice,
            result=result,
            ckpt_manager=ckpt_manager,
            storage_gateway=storage_gateway,
        )

    return result


def _prepare_summarize_request(data, runtime):
    request_data = SummarizeRequest.from_payload(data, runtime.clean_vndb_data, extract_file_paths)

    if not request_data.role_name:
        return None, fail_result('请输入角色名称')

    config = build_llm_config(data)
    checkpoint_id = None

    if request_data.resume_checkpoint_id:
        ckpt_result = load_resumable_checkpoint(runtime.checkpoint_gateway, request_data.resume_checkpoint_id)
        if not ckpt_result.get('success'):
            return None, ckpt_result
        ckpt = ckpt_result['checkpoint']

        request_data.apply_checkpoint(ckpt['input_params'])
        checkpoint_id = request_data.resume_checkpoint_id
        _sanitize_resume_progress(ckpt, runtime.checkpoint_gateway, checkpoint_id)

        completed_indices = set(ckpt['progress'].get('completed_items', []))
        print(f"Resuming summarize: {len(completed_indices)}/{ckpt['progress'].get('total_steps', '?')} slices already done")
    else:
        if not request_data.file_paths:
            return None, fail_result('请先选择文件')

        checkpoint_id = runtime.checkpoint_gateway.create_checkpoint(
            task_type='summarize',
            input_params=request_data.to_checkpoint_input()
        )

    if not request_data.file_paths:
        return None, fail_result('请先选择文件')

    return {
        'request_data': request_data,
        'config': config,
        'checkpoint_id': checkpoint_id,
    }, None


def _sanitize_resume_progress(ckpt, checkpoint_gateway, checkpoint_id):
    if ckpt.get('task_type') != 'summarize':
        return

    progress = ckpt.get('progress', {})
    completed = list(progress.get('completed_items', []))
    if not completed:
        return

    valid_completed = []
    invalid_completed = []
    for index in completed:
        content = checkpoint_gateway.get_slice_result(checkpoint_id, index)
        if isinstance(content, str) and content.strip():
            valid_completed.append(index)
        else:
            invalid_completed.append(index)

    if not invalid_completed:
        return

    pending = list(progress.get('pending_items', []))
    pending_set = set(pending)
    for index in invalid_completed:
        pending_set.add(index)
    pending_clean = [index for index in sorted(pending_set) if index not in set(valid_completed)]

    progress['completed_items'] = valid_completed
    progress['pending_items'] = pending_clean
    checkpoint_gateway.update_progress(
        checkpoint_id,
        completed_items=valid_completed,
        pending_items=pending_clean,
    )


def _build_summary_dir(file_paths, role_name):
    if len(file_paths) == 1:
        file_name = os.path.basename(file_paths[0])
        name, _ = os.path.splitext(file_name)
        return os.path.join(os.path.dirname(file_paths[0]), f"{name}_summaries")

    first_dir = os.path.dirname(file_paths[0])
    name = os.path.basename(file_paths[0])
    name = os.path.splitext(name)[0]
    return os.path.join(first_dir, f"{name}_merged_summaries")


def _build_slice_tasks(current_slices, summary_dir, request_data, config, checkpoint_id):
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
            checkpoint_id,
        ))
    return tasks


def _execute_slice_tasks(tasks, request_data, runtime):
    summaries = []
    errors = []
    all_results = []
    all_character_analyses = []
    all_lorebook_entries = []

    with runtime.executor_gateway.create(max_workers=request_data.concurrency) as executor:
        future_to_task = {
            executor.submit(
                _process_single_slice,
                task,
                runtime.checkpoint_gateway,
                runtime.llm_gateway,
                runtime.tool_gateway,
                runtime.storage_gateway,
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

    return {
        'summaries': summaries,
        'errors': errors,
        'all_results': all_results,
        'all_character_analyses': all_character_analyses,
        'all_lorebook_entries': all_lorebook_entries,
    }


def _finalize_summarize_result(request_data, current_slices, summary_dir, execution, checkpoint_id, runtime):
    if request_data.mode == 'chara_card':
        analysis_summary_path = os.path.join(summary_dir, f"{request_data.role_name}_analysis_summary.json")
        runtime.storage_gateway.write_json(
            analysis_summary_path,
            {
                'character_analyses': execution['all_character_analyses'],
                'lorebook_entries': execution['all_lorebook_entries'],
            },
            ensure_ascii=False,
            indent=2,
        )

    if execution['errors'] and len(execution['summaries']) == 0:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, f"{len(execution['errors'])} 个切片全部失败")
        return fail_result(
            f"归纳失败，{len(execution['errors'])} 个切片失败",
            slice_count=len(current_slices),
            errors=execution['errors'],
            results=execution['all_results'],
            checkpoint_id=checkpoint_id,
            can_resume=True,
        )

    if execution['errors']:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, f"{len(execution['errors'])} 个切片失败，可恢复继续处理")
        return ok_result(
            message=f"归纳部分完成，{len(execution['errors'])} 个切片失败，可通过任务列表继续",
            slice_count=len(current_slices),
            errors=execution['errors'],
            results=execution['all_results'],
            checkpoint_id=checkpoint_id,
            can_resume=True,
        )

    runtime.checkpoint_gateway.mark_completed(checkpoint_id)
    return ok_result(
        message='归纳完成',
        slice_count=len(current_slices),
        results=execution['all_results'],
        checkpoint_id=checkpoint_id,
    )


def run_summarize_task(data, runtime):
    prepared, error = _prepare_summarize_request(data, runtime)
    if error:
        return error

    request_data = prepared['request_data']
    config = prepared['config']
    checkpoint_id = prepared['checkpoint_id']

    current_slices = runtime.file_processor.slice_multiple_files(request_data.file_paths, request_data.slice_size_k)
    runtime.llm_gateway.set_total_requests(len(current_slices))

    summary_dir = _build_summary_dir(request_data.file_paths, request_data.role_name)
    runtime.storage_gateway.makedirs(summary_dir, exist_ok=True)

    if not request_data.resume_checkpoint_id:
        runtime.checkpoint_gateway.update_progress(
            checkpoint_id,
            total_steps=len(current_slices),
            pending_items=list(range(len(current_slices)))
        )

    tasks = _build_slice_tasks(current_slices, summary_dir, request_data, config, checkpoint_id)
    execution = _execute_slice_tasks(tasks, request_data, runtime)

    return _finalize_summarize_result(
        request_data=request_data,
        current_slices=current_slices,
        summary_dir=summary_dir,
        execution=execution,
        checkpoint_id=checkpoint_id,
        runtime=runtime,
    )
