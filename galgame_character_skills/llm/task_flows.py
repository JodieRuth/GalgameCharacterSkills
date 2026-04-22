"""角色卡任务流辅助模块，提供字段初始化、消息构建与结果封装。"""

import os
from datetime import datetime
from typing import Any

from ..utils.prompt_builders import build_character_card_user_prompt


def build_write_field_tools() -> list[dict[str, Any]]:
    """构造 write_field 工具定义。

    Args:
        None

    Returns:
        list[dict[str, Any]]: 工具定义列表。

    Raises:
        Exception: 工具定义构造失败时向上抛出。
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "write_field",
                "description": "Write a specific field to the character card JSON file. Call this tool multiple times to write different fields.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_name": {
                            "type": "string",
                            "description": "The name of the field to write. Must be one of: name, description, personality, first_mes, mes_example, scenario, system_prompt, post_history_instructions, depth_prompt",
                            "enum": [
                                "name",
                                "description",
                                "personality",
                                "first_mes",
                                "mes_example",
                                "scenario",
                                "system_prompt",
                                "post_history_instructions",
                                "depth_prompt",
                            ],
                        },
                        "content": {
                            "type": "string",
                            "description": "The content to write for this field. For string fields, provide the text. For list fields (like personality traits), provide a JSON array string.",
                        },
                        "is_complete": {
                            "type": "boolean",
                            "description": "Set to true if this is the last field you want to write. The system will finalize the character card after this.",
                        },
                    },
                    "required": ["field_name", "content"],
                },
            },
        }
    ]


def build_initial_character_card_fields(
    role_name: str,
    creator: str,
    vndb_data: dict[str, Any] | None,
    lorebook_entries: list[Any],
) -> dict[str, Any]:
    """构造角色卡初始字段。

    Args:
        role_name: 角色名。
        creator: 创作者名。
        vndb_data: VNDB 数据。
        lorebook_entries: lorebook 条目列表。

    Returns:
        dict[str, Any]: 初始字段映射。

    Raises:
        Exception: 字段构造失败时向上抛出。
    """
    base_name = role_name
    if vndb_data and vndb_data.get("name"):
        base_name = vndb_data["name"]

    return {
        "name": base_name,
        "description": "",
        "personality": "",
        "first_mes": "",
        "mes_example": "",
        "scenario": "",
        "system_prompt": "",
        "post_history_instructions": "",
        "depth_prompt": "",
        "creatorcomment": f"Character card for {base_name}" + (f" (VNDB: {vndb_data.get('vndb_id', '')})" if vndb_data else ""),
        "world_name": base_name,
        "create_date": datetime.now().isoformat(),
        "creator": creator or "AI Character Generator",
        "tags": ["character", base_name.lower().replace(" ", "_")],
        "character_book_entries": lorebook_entries,
    }


def apply_checkpoint_fields(
    fields_data: dict[str, Any],
    ckpt_fields_data: dict[str, Any] | None,
) -> None:
    """将 checkpoint 字段回填到当前字段数据。

    Args:
        fields_data: 当前字段数据。
        ckpt_fields_data: checkpoint 字段数据。

    Returns:
        None

    Raises:
        Exception: 字段回填失败时向上抛出。
    """
    if not ckpt_fields_data:
        return
    for key in fields_data:
        if key in ckpt_fields_data and ckpt_fields_data[key]:
            if key == "character_book_entries":
                continue
            fields_data[key] = ckpt_fields_data[key]


def build_character_card_messages(
    is_resuming: bool,
    ckpt_messages: list[dict[str, Any]] | None,
    ckpt_iteration_count: int | None,
    system_prompt: str,
    role_name: str,
) -> tuple[list[dict[str, Any]], int]:
    """构造角色卡生成消息列表。

    Args:
        is_resuming: 是否为恢复执行。
        ckpt_messages: checkpoint 消息列表。
        ckpt_iteration_count: checkpoint 迭代次数。
        system_prompt: 系统提示词。
        role_name: 角色名。

    Returns:
        tuple[list[dict[str, Any]], int]: 消息列表和起始迭代次数。

    Raises:
        Exception: 消息构造失败时向上抛出。
    """
    if is_resuming:
        return ckpt_messages, ckpt_iteration_count or 0
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_character_card_user_prompt(role_name)},
    ], 0


def build_character_card_template_path() -> str:
    """获取角色卡模板路径。

    Args:
        None

    Returns:
        str: 模板文件路径。

    Raises:
        Exception: 路径构造失败时向上抛出。
    """
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "utils", "chara_card_template.json")


def build_character_card_field_mappings(fields_data: dict[str, Any]) -> dict[str, Any]:
    """构造角色卡模板字段映射。

    Args:
        fields_data: 字段数据。

    Returns:
        dict[str, Any]: 模板字段映射。

    Raises:
        Exception: 字段映射构造失败时向上抛出。
    """
    return {
        "{{name}}": fields_data["name"],
        "{{description}}": fields_data["description"],
        "{{personality}}": fields_data["personality"],
        "{{first_mes}}": fields_data["first_mes"],
        "{{mes_example}}": fields_data["mes_example"],
        "{{scenario}}": fields_data["scenario"],
        "{{create_date}}": fields_data["create_date"],
        "{{creatorcomment}}": fields_data["creatorcomment"],
        "{{system_prompt}}": fields_data["system_prompt"],
        "{{post_history_instructions}}": fields_data["post_history_instructions"],
        "{{tags}}": fields_data["tags"],
        "{{creator}}": fields_data["creator"],
        "{{world_name}}": fields_data["world_name"],
        "{{depth_prompt}}": fields_data["depth_prompt"],
        "{{character_book_entries}}": fields_data["character_book_entries"],
    }


def build_character_card_success_result(
    output_path: str,
    fields_data: dict[str, Any],
    result: Any,
) -> dict[str, Any]:
    """构造角色卡生成成功结果。

    Args:
        output_path: 输出路径。
        fields_data: 字段数据。
        result: 模板写入结果。

    Returns:
        dict[str, Any]: 成功结果字典。

    Raises:
        Exception: 结果构造失败时向上抛出。
    """
    return {
        "success": True,
        "output_path": output_path,
        "fields_written": [k for k, v in fields_data.items() if v and k != "character_book_entries"],
        "result": result,
    }


__all__ = [
    "build_write_field_tools",
    "build_initial_character_card_fields",
    "apply_checkpoint_fields",
    "build_character_card_messages",
    "build_character_card_template_path",
    "build_character_card_field_mappings",
    "build_character_card_success_result",
]
