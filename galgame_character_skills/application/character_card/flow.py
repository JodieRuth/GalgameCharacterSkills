"""角色卡生成流程编排。"""

import json
from typing import Any, Callable

from ...llm.card_prompt_builders import (
    build_character_card_language_instruction,
    build_character_card_system_prompt,
    build_integrate_analyses_system_prompt,
    build_integrate_analyses_user_prompt,
)
from ...llm.character_card_fields import (
    apply_checkpoint_fields,
    build_character_card_field_mappings,
    build_character_card_messages,
    build_character_card_success_result,
    build_character_card_template_path,
    build_initial_character_card_fields,
    build_write_field_tools,
)
from .tool_loop import run_character_card_tool_loop


def integrate_character_analyses(
    *,
    send_message: Callable[..., Any],
    tool_gateway: Any,
    role_name: str,
    all_analyses: list[dict[str, Any]],
    vndb_data: dict[str, Any] | None,
    format_vndb_section: Callable[[dict[str, Any] | None, str, str], str],
) -> dict[str, Any]:
    """整合多份角色分析结果。"""
    vndb_section = format_vndb_section(vndb_data, "## VNDB Character Information", bullet="")
    system_prompt = build_integrate_analyses_system_prompt(role_name, vndb_section)
    analyses_json = json.dumps(all_analyses, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_integrate_analyses_user_prompt(role_name, analyses_json)},
    ]

    response = send_message(messages, use_counter=False)
    if response and response.choices:
        content = response.choices[0].message.content
        return tool_gateway.parse_llm_json_response(content) or {}
    return {}


def generate_character_card(
    *,
    send_message: Callable[..., Any],
    tool_gateway: Any,
    lang_names: dict[str, str],
    format_vndb_section: Callable[[dict[str, Any] | None, str, str], str],
    role_name: str,
    all_analyses: list[dict[str, Any]],
    all_lorebook_entries: list[Any],
    output_path: str,
    creator: str = "",
    vndb_data: dict[str, Any] | None = None,
    output_language: str = "",
    checkpoint_id: str | None = None,
    ckpt_messages: list[dict[str, Any]] | None = None,
    ckpt_fields_data: dict[str, Any] | None = None,
    ckpt_iteration_count: int | None = None,
    save_llm_state_fn: Any = None,
) -> dict[str, Any]:
    """执行角色卡生成流程。"""
    integrated_analysis = integrate_character_analyses(
        send_message=send_message,
        tool_gateway=tool_gateway,
        role_name=role_name,
        all_analyses=all_analyses,
        vndb_data=vndb_data,
        format_vndb_section=format_vndb_section,
    )

    vndb_ref = format_vndb_section(
        vndb_data,
        "VNDB REFERENCE DATA (HIGHEST PRIORITY - Use these values as authoritative source for character appearance and basic info)",
        bullet="",
    )

    tools = build_write_field_tools()
    merged_entries = tool_gateway.merge_lorebook_entries(all_lorebook_entries)
    lorebook_entries = tool_gateway.build_lorebook_entries(merged_entries, start_id=0)
    fields_data = build_initial_character_card_fields(
        role_name=role_name,
        creator=creator,
        vndb_data=vndb_data,
        lorebook_entries=lorebook_entries,
    )

    is_resuming = ckpt_messages is not None and len(ckpt_messages) > 0
    if is_resuming:
        apply_checkpoint_fields(fields_data, ckpt_fields_data)

    language_instruction = build_character_card_language_instruction(output_language, lang_names)
    integrated_analysis_json = json.dumps(integrated_analysis, ensure_ascii=False, indent=2)
    system_prompt = build_character_card_system_prompt(
        role_name=role_name,
        integrated_analysis_json=integrated_analysis_json,
        vndb_ref=vndb_ref,
        language_instruction=language_instruction,
    )

    messages, tool_call_count = build_character_card_messages(
        is_resuming=is_resuming,
        ckpt_messages=ckpt_messages,
        ckpt_iteration_count=ckpt_iteration_count,
        system_prompt=system_prompt,
        role_name=role_name,
    )

    loop_result = run_character_card_tool_loop(
        send_message=send_message,
        tool_gateway=tool_gateway,
        tools=tools,
        messages=messages,
        fields_data=fields_data,
        checkpoint_id=checkpoint_id,
        initial_tool_call_count=tool_call_count,
        max_tool_calls=50,
        save_llm_state_fn=save_llm_state_fn,
    )
    if not loop_result.get("success"):
        return loop_result

    template_path = build_character_card_template_path()
    field_mappings = build_character_card_field_mappings(fields_data)
    result = tool_gateway.fill_json_template(template_path, output_path, field_mappings)
    return build_character_card_success_result(
        output_path=output_path,
        fields_data=fields_data,
        result=result,
    )


__all__ = ["integrate_character_analyses", "generate_character_card"]
