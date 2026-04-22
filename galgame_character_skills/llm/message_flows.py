"""LLM 消息构造与发送辅助流程。"""

from typing import Any, Callable

from .prompts import (
    build_summarize_content_payload,
    build_summarize_chara_card_payload,
    build_generate_skills_folder_init_payload,
    build_compress_content_payload,
)


def send_summarize_content(
    *,
    send_message: Callable[..., Any],
    lang_names: dict[str, str],
    format_vndb_section: Callable[[dict[str, Any] | None, str], str],
    content: str,
    role_name: str,
    instruction: str,
    output_file_path: str,
    output_language: str = "",
    vndb_data: dict[str, Any] | None = None,
) -> Any:
    """构造并发送文本归纳请求。"""
    messages, tools = build_summarize_content_payload(
        content=content,
        role_name=role_name,
        instruction=instruction,
        output_file_path=output_file_path,
        output_language=output_language,
        vndb_data=vndb_data,
        lang_names=lang_names,
        format_vndb_section=format_vndb_section,
    )
    return send_message(messages, tools)


def send_summarize_chara_card_content(
    *,
    send_message: Callable[..., Any],
    lang_names: dict[str, str],
    format_vndb_section: Callable[[dict[str, Any] | None, str], str],
    content: str,
    role_name: str,
    instruction: str,
    output_file_path: str,
    output_language: str = "",
    vndb_data: dict[str, Any] | None = None,
) -> Any:
    """构造并发送角色卡分析归纳请求。"""
    messages, tools = build_summarize_chara_card_payload(
        content=content,
        role_name=role_name,
        instruction=instruction,
        output_file_path=output_file_path,
        output_language=output_language,
        vndb_data=vndb_data,
        lang_names=lang_names,
        format_vndb_section=format_vndb_section,
    )
    return send_message(messages, tools)


def build_skills_init_messages(
    *,
    lang_names: dict[str, str],
    format_vndb_section: Callable[[dict[str, Any] | None, str], str],
    summaries: str,
    role_name: str,
    output_language: str = "",
    vndb_data: dict[str, Any] | None = None,
    output_root_dir: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """构造技能包初始化消息和工具定义。"""
    return build_generate_skills_folder_init_payload(
        summaries=summaries,
        role_name=role_name,
        output_root_dir=output_root_dir,
        output_language=output_language,
        vndb_data=vndb_data,
        lang_names=lang_names,
        format_vndb_section=format_vndb_section,
    )


def build_compression_messages(
    group_files_content: dict[str, str],
    group_info: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """构造压缩请求消息和工具定义。"""
    return build_compress_content_payload(
        group_files_content=group_files_content,
        group_info=group_info,
    )


__all__ = [
    "send_summarize_content",
    "send_summarize_chara_card_content",
    "build_skills_init_messages",
    "build_compression_messages",
]
