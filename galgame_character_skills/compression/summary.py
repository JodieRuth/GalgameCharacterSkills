"""Summary 文件压缩模块。"""

import json
import math
import os
import shutil
from typing import Any, Callable

from .common import (
    append_tool_exchange_messages,
    build_group_info,
    cleanup_temp_workspace,
    create_temp_workspace,
)
from ..llm.message_flows import build_compression_messages


def compress_summary_files_with_llm(
    summary_files: list[str],
    llm_client: Any,
    target_budget_tokens: int = 115000,
    checkpoint_id: str | None = None,
    ckpt_manager: Any = None,
    estimate_tokens: Callable[[str], int] | None = None,
) -> str:
    """使用 LLM 压缩 summary 文件集合。

    Args:
        summary_files: summary 文件路径列表。
        llm_client: LLM 客户端。
        target_budget_tokens: 目标 token 预算。
        checkpoint_id: checkpoint 标识。
        ckpt_manager: checkpoint 管理器。
        estimate_tokens: token 估算函数。

    Returns:
        str: 压缩后的聚合文本。

    Raises:
        Exception: 文件读写或压缩过程异常未被内部拦截时向上抛出。
    """
    print(f"Starting LLM-based compression for {len(summary_files)} files")

    total_tokens = 0
    file_contents: dict[str, str] = {}
    file_path_map: dict[str, str] = {}

    for file_path in summary_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
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

    temp_dir = create_temp_workspace(
        checkpoint_id=checkpoint_id,
        ckpt_manager=ckpt_manager,
        workspace_name="llm_compression",
    )
    temp_file_map: dict[str, str] = {}

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

        group_files_content: dict[str, str] = {}
        group_file_map: dict[str, str] = {}
        group_tokens = 0
        for fp in group_files:
            basename = os.path.basename(fp)
            if basename in file_contents:
                group_files_content[basename] = file_contents[basename]
                group_tokens += estimate_tokens(file_contents[basename])
                if basename in temp_file_map:
                    group_file_map[basename] = temp_file_map[basename]

        print(f"Processing group {group_idx + 1}/{num_groups}: {len(group_files)} files, ~{group_tokens} tokens")

        group_info = build_group_info(group_idx, num_groups, len(group_files))
        messages, tools = build_compression_messages(group_files_content, group_info)

        try:
            max_iterations = 50
            iteration = 0
            total_processed = 0

            while iteration < max_iterations:
                iteration += 1
                response = llm_client.send_message(messages, tools, max_retries=2, use_counter=False)

                if not response or not hasattr(response, "choices") or not response.choices:
                    print(f"Warning: LLM returned no response for group {group_idx + 1}, iteration {iteration}")
                    break

                message = response.choices[0].message

                if not hasattr(message, "tool_calls") or not message.tool_calls:
                    print(f"Group {group_idx + 1}: No more tool calls after {iteration} iterations")
                    break

                tool_results = []
                has_remove_call = False

                for tool_call in message.tool_calls:
                    if tool_call.function.name == "remove_duplicate_sections":
                        has_remove_call = True
                        arguments = json.loads(tool_call.function.arguments)
                        file_sections = arguments.get("file_sections", [])

                        duplicate_tracking: dict[str, list[tuple[str, str]]] = {}

                        for section in file_sections:
                            filename = section.get("filename", "")
                            content = section.get("content", "")
                            if not content or not filename:
                                continue

                            if filename in group_file_map:
                                temp_path = group_file_map[filename]
                                duplicate_tracking.setdefault(content, []).append((filename, temp_path))

                        processed_count = 0
                        for content, file_list in duplicate_tracking.items():
                            if len(file_list) <= 1:
                                continue

                            for filename, temp_path in file_list[1:]:
                                try:
                                    with open(temp_path, "r", encoding="utf-8") as f:
                                        file_content = f.read()

                                    if content in file_content:
                                        new_content = file_content.replace(content, "")
                                        with open(temp_path, "w", encoding="utf-8") as f:
                                            f.write(new_content)
                                        processed_count += 1
                                except Exception as e:
                                    print(f"  - Error processing {filename}: {e}")

                        total_processed += processed_count
                        tool_results.append(
                            {
                                "tool_call_id": tool_call.id if hasattr(tool_call, "id") else tool_call.get("id"),
                                "result": f"Removed duplicates from {processed_count} files",
                            }
                        )

                if not has_remove_call:
                    print(f"Warning: LLM did not call remove_duplicate_sections in iteration {iteration}")
                    break

                append_tool_exchange_messages(messages, message, tool_results)
                print(
                    f"Group {group_idx + 1}, iteration {iteration}: "
                    f"processed {len(tool_results)} tool calls, removed from {total_processed} files so far"
                )

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
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            final_content_parts.append(f"=== {basename} ===\n{content}")
            final_tokens += estimate_tokens(content)
        except Exception as e:
            print(f"Warning: Failed to read temp file {temp_path}: {e}")
            final_content_parts.append(f"=== {basename} ===\n{file_contents[basename]}")
            final_tokens += estimate_tokens(file_contents[basename])

    cleanup_temp_workspace(temp_dir)

    final_content = "\n\n".join(final_content_parts)
    print(f"Final result: {total_tokens} -> {final_tokens} tokens ({final_tokens / total_tokens * 100:.1f}%)")
    return final_content
