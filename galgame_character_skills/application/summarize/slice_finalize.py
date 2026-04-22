"""summarize 单片结果收尾模块。"""

import json
from typing import Any

from .models import SliceExecutionResult


def extract_write_file_content(choice: Any) -> str:
    """提取 write_file 工具中的文本内容。"""
    if not (hasattr(choice, "message") and hasattr(choice.message, "tool_calls") and choice.message.tool_calls):
        return ""
    for tool_call in choice.message.tool_calls:
        if hasattr(tool_call, "function") and tool_call.function.name == "write_file":
            try:
                args_dict = json.loads(tool_call.function.arguments)
            except Exception:
                return ""
            return args_dict.get("content", "") or ""
    return ""


def finalize_skills_slice_result(
    result: SliceExecutionResult,
    choice: Any,
    output_file_path: str,
    storage_gateway: Any,
) -> None:
    """完成 skills 模式切片结果落盘。"""
    content_from_tool = extract_write_file_content(choice)
    content = content_from_tool or (result.summary or "")
    if not content.strip():
        result.success = False
        result.summary = None
        result.tool_results.append("Empty summary content")
        return

    if not content_from_tool:
        storage_gateway.write_text(output_file_path, content)
        result.summary = content

    if not storage_gateway.exists(output_file_path):
        result.success = False
        result.summary = None
        result.tool_results.append("Summary file was not saved")


def build_restored_slice_result(
    slice_index: int,
    mode: str,
    output_file_path: str,
    storage_gateway: Any,
) -> SliceExecutionResult:
    """构造从 checkpoint 恢复的切片结果。"""
    result = SliceExecutionResult(
        index=slice_index,
        success=True,
        summary=f"Slice {slice_index + 1} restored from checkpoint",
        output_path=output_file_path,
        restored=True,
    )

    if mode == "chara_card":
        try:
            if not storage_gateway.exists(output_file_path):
                return result
            parsed = storage_gateway.read_json(output_file_path)
            result.character_analysis = parsed.get("character_analysis", {})
            result.lorebook_entries = parsed.get("lorebook_entries", [])
        except Exception:
            pass
        return result

    try:
        if not storage_gateway.exists(output_file_path):
            return result
        content = storage_gateway.read_text(output_file_path)
        result.summary = content[:200] + "..." if len(content) > 200 else content
    except Exception:
        pass
    return result


def handle_chara_card_slice_choice(
    result: SliceExecutionResult,
    choice: Any,
    output_file_path: str,
    tool_gateway: Any,
    storage_gateway: Any,
) -> None:
    """处理 chara_card 模式的单片响应。"""
    if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
        for tool_call in choice.message.tool_calls:
            tool_result = tool_gateway.handle_tool_call(tool_call)
            result.tool_results.append(tool_result)
        result.success = True
        result.summary = f"Slice {result.index + 1} saved to {output_file_path}"

        try:
            parsed = storage_gateway.read_json(output_file_path)
            result.character_analysis = parsed.get("character_analysis", {})
            result.lorebook_entries = parsed.get("lorebook_entries", [])
        except Exception as exc:
            result.tool_results.append(f"Warning: Failed to read saved file: {exc}")
        return

    if hasattr(choice, "message") and choice.message.content:
        parsed = tool_gateway.parse_llm_json_response(choice.message.content)
        if parsed:
            result.character_analysis = parsed.get("character_analysis", {})
            result.lorebook_entries = parsed.get("lorebook_entries", [])
            result.success = True
            result.summary = f"Slice {result.index + 1} analyzed successfully"
            storage_gateway.write_json(output_file_path, parsed, ensure_ascii=False, indent=2)


def handle_skills_slice_choice(
    result: SliceExecutionResult,
    choice: Any,
    output_file_path: str,
    tool_gateway: Any,
    storage_gateway: Any,
) -> None:
    """处理 skills 模式的单片响应。"""
    if hasattr(choice, "message") and hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
        for tool_call in choice.message.tool_calls:
            tool_result = tool_gateway.handle_tool_call(tool_call)
            result.tool_results.append(tool_result)
        result.success = True
        result.summary = f"Slice {result.index + 1} saved to {output_file_path}"
    else:
        result.success = True
        result.summary = choice.message.content
    finalize_skills_slice_result(result, choice, output_file_path, storage_gateway)


__all__ = [
    "build_restored_slice_result",
    "extract_write_file_content",
    "finalize_skills_slice_result",
    "handle_chara_card_slice_choice",
    "handle_skills_slice_choice",
]
