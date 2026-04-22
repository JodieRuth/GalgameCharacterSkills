"""分析结果压缩模块。"""

import json
import math
import os
from typing import Any, Callable

from .common import (
    append_tool_exchange_messages,
    build_group_info,
    cleanup_temp_workspace,
    create_temp_workspace,
)
from ..llm.message_flows import build_compression_messages


def compress_analyses_with_llm(
    analyses: list[dict[str, Any]],
    llm_client: Any,
    target_budget_tokens: int = 115000,
    checkpoint_id: str | None = None,
    ckpt_manager: Any = None,
    estimate_tokens: Callable[[str], int] | None = None,
) -> list[dict[str, Any]]:
    """使用 LLM 压缩分析结果集合。

    Args:
        analyses: 分析结果列表。
        llm_client: LLM 客户端。
        target_budget_tokens: 目标 token 预算。
        checkpoint_id: checkpoint 标识。
        ckpt_manager: checkpoint 管理器。
        estimate_tokens: token 估算函数。

    Returns:
        list[dict[str, Any]]: 压缩后的分析结果列表。

    Raises:
        Exception: 文件读写或压缩过程异常未被内部拦截时向上抛出。
    """
    print(f"Starting compression for {len(analyses)} analyses")

    total_tokens = 0
    analysis_contents: dict[str, str] = {}
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

    temp_dir = create_temp_workspace(
        checkpoint_id=checkpoint_id,
        ckpt_manager=ckpt_manager,
        workspace_name="analyses_compression",
    )
    temp_file_map: dict[str, str] = {}

    for key, content in analysis_contents.items():
        temp_path = os.path.join(temp_dir, f"{key}.json")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
        temp_file_map[key] = temp_path

    print(f"Created temp workspace: {temp_dir}")

    for group_idx in range(num_groups):
        start_idx = group_idx * analyses_per_group
        end_idx = min((group_idx + 1) * analyses_per_group, len(analyses))
        group_keys = list(analysis_contents.keys())[start_idx:end_idx]

        if not group_keys:
            continue

        group_files_content: dict[str, str] = {}
        group_file_map: dict[str, str] = {}
        group_tokens = 0
        for key in group_keys:
            with open(temp_file_map[key], "r", encoding="utf-8") as f:
                content = f.read()
            group_files_content[f"{key}.json"] = content
            group_tokens += estimate_tokens(content)
            group_file_map[key] = temp_file_map[key]

        print(f"Processing group {group_idx + 1}/{num_groups}: {len(group_keys)} analyses, ~{group_tokens} tokens")

        group_info = build_group_info(group_idx, num_groups, len(group_keys))
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

                        processed_count = 0
                        for section in file_sections:
                            filename = section.get("filename", "")
                            content_to_remove = section.get("content", "")
                            key = filename.replace(".json", "")
                            if key in group_file_map:
                                temp_path = group_file_map[key]
                                try:
                                    with open(temp_path, "r", encoding="utf-8") as f:
                                        file_content = f.read()
                                    if content_to_remove in file_content:
                                        new_content = file_content.replace(content_to_remove, "")
                                        with open(temp_path, "w", encoding="utf-8") as f:
                                            f.write(new_content)
                                        processed_count += 1
                                except Exception as e:
                                    print(f"Error processing {filename}: {e}")

                        total_processed += processed_count
                        tool_results.append(
                            {
                                "tool_call_id": tool_call.id if hasattr(tool_call, "id") else tool_call.get("id"),
                                "result": f"Removed {processed_count} sections",
                            }
                        )

                if not has_remove_call:
                    print(f"Warning: LLM did not call remove_duplicate_sections in iteration {iteration}")
                    break

                append_tool_exchange_messages(messages, message, tool_results)
                print(
                    f"Group {group_idx + 1}, iteration {iteration}: "
                    f"processed {len(tool_results)} tool calls, removed {total_processed} sections so far"
                )

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
            with open(temp_path, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                analysis = json.loads(content)
                compressed_analyses.append(analysis)
                final_tokens += estimate_tokens(content)
        except Exception as e:
            print(f"Warning: Failed to read temp file {temp_path}: {e}")
            compressed_analyses.append(analyses[idx])
            final_tokens += estimate_tokens(analysis_contents[key])

    cleanup_temp_workspace(temp_dir)

    print(
        f"Final result: {len(analyses)} analyses, "
        f"{total_tokens} -> {final_tokens} tokens ({final_tokens / total_tokens * 100:.1f}%)"
    )
    return compressed_analyses
