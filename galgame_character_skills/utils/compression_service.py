import json
import math
import os
import shutil
import tempfile


def compress_summary_files_with_llm(
    summary_files,
    llm_client,
    target_budget_tokens=115000,
    checkpoint_id=None,
    ckpt_manager=None,
    estimate_tokens=None
):
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
            total_tokens += estimate_tokens(content)
        except Exception as e:
            print(f"Warning: Failed to read {file_path}: {e}")
            continue

    print(f"Total tokens: {total_tokens}")

    if total_tokens <= target_budget_tokens:
        print(f"Total tokens ({total_tokens}) <= target ({target_budget_tokens}), skipping compression")
        return "\n\n".join([f"=== {basename} ===\n{content}" for basename, content in file_contents.items()])

    if checkpoint_id:
        ckpt_temp_dir = ckpt_manager.get_temp_dir(checkpoint_id)
        temp_dir = os.path.join(ckpt_temp_dir, 'llm_compression')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
                group_tokens += estimate_tokens(file_contents[basename])
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
            final_tokens += estimate_tokens(content)
        except Exception as e:
            print(f"Warning: Failed to read temp file {temp_path}: {e}")
            final_content_parts.append(f"=== {basename} ===\n{file_contents[basename]}")
            final_tokens += estimate_tokens(file_contents[basename])

    try:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp workspace: {temp_dir}")
    except Exception as e:
        print(f"Warning: Failed to cleanup temp dir: {e}")

    final_content = "\n\n".join(final_content_parts)
    print(f"Final result: {total_tokens} -> {final_tokens} tokens ({final_tokens/total_tokens*100:.1f}%)")
    return final_content


def compress_analyses_with_llm(
    analyses,
    llm_client,
    target_budget_tokens=115000,
    checkpoint_id=None,
    ckpt_manager=None,
    estimate_tokens=None
):
    print(f"Starting compression for {len(analyses)} analyses")

    total_tokens = 0
    analysis_contents = {}
    for idx, analysis in enumerate(analyses):
        key = f"analysis_{idx:03d}"
        content = json.dumps(analysis, ensure_ascii=False)
        analysis_contents[key] = content
        total_tokens += estimate_tokens(content)

    print(f"Total tokens: {total_tokens}")

    if total_tokens <= target_budget_tokens:
        print(f"Total tokens ({total_tokens}) <= target ({target_budget_tokens}), skipping compression")
        return analyses

    tokens_per_group = 100000
    num_groups = max(1, math.ceil(total_tokens / tokens_per_group))
    analyses_per_group = math.ceil(len(analyses) / num_groups)
    print(f"Dividing into {num_groups} groups, ~{analyses_per_group} analyses per group")

    if checkpoint_id:
        ckpt_temp_dir = ckpt_manager.get_temp_dir(checkpoint_id)
        temp_dir = os.path.join(ckpt_temp_dir, 'analyses_compression')
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
            group_tokens += estimate_tokens(content)
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
                final_tokens += estimate_tokens(content)
        except Exception as e:
            print(f"Warning: Failed to read temp file {temp_path}: {e}")
            compressed_analyses.append(analyses[idx])
            final_tokens += estimate_tokens(analysis_contents[key])

    try:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp workspace: {temp_dir}")
    except Exception as e:
        print(f"Warning: Failed to cleanup temp dir: {e}")

    print(f"Final result: {len(analyses)} analyses, {total_tokens} -> {final_tokens} tokens ({final_tokens/total_tokens*100:.1f}%)")
    return compressed_analyses
