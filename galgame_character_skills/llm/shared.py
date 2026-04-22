"""LLM 任务流共享常量与格式化辅助。"""

from typing import Any


LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語"}


def format_vndb_section(
    vndb_data: dict[str, Any] | None,
    title: str,
    bullet: str = "-",
) -> str:
    """格式化 VNDB 信息段落。"""
    if not vndb_data:
        return ""

    entries = []
    field_map = [
        ("name", "Name"),
        ("original_name", "Original Name"),
        ("aliases", "Aliases"),
        ("description", "Description"),
        ("age", "Age"),
        ("birthday", "Birthday"),
        ("blood_type", "Blood Type"),
        ("height", "Height"),
        ("weight", "Weight"),
        ("traits", "Traits"),
        ("vns", "Visual Novels"),
    ]

    for key, label in field_map:
        value = vndb_data.get(key)
        if not value:
            continue
        if key == "aliases" and isinstance(value, list):
            value = ", ".join(value)
        elif key == "traits" and isinstance(value, list):
            value = ", ".join(value)
        elif key == "vns" and isinstance(value, list):
            value = ", ".join(value[:3])
        elif key == "height":
            value = f"{value}cm"
        elif key == "weight":
            value = f"{value}kg"
        prefix = f"{bullet} " if bullet else ""
        entries.append(f"{prefix}{label}: {value}")

    if vndb_data.get("bust") and vndb_data.get("waist") and vndb_data.get("hips"):
        prefix = f"{bullet} " if bullet else ""
        entries.append(f"{prefix}Measurements: {vndb_data['bust']}-{vndb_data['waist']}-{vndb_data['hips']}cm")

    if not entries:
        return ""

    return f"\n\n{title}\n" + "\n".join(entries) + "\n"


__all__ = ["LANG_NAMES", "format_vndb_section"]
