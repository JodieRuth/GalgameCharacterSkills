"""技能产物后处理模块，负责追加 VNDB 信息并同步生成代码版技能目录。"""

import os
from typing import Any

_VNDB_SECTION_PREFIX_LINES = ["", "", "---", ""]
_VNDB_SECTION_TITLE = "## VNDB Character Information"


_VNDB_FIELD_LABELS = [
    ("name", "Name"),
    ("original_name", "Original Name"),
    ("description", "Description"),
    ("age", "Age"),
    ("birthday", "Birthday"),
    ("blood_type", "Blood Type"),
]

_VNDB_OPTIONAL_RENDERERS = [
    lambda d: _render_joined_list_line("Aliases", d.get("aliases")),
    lambda d: _render_measurement_line("Height", d.get("height"), "cm"),
    lambda d: _render_measurement_line("Weight", d.get("weight"), "kg"),
    lambda d: _render_measurements_line(d.get("bust"), d.get("waist"), d.get("hips")),
    lambda d: _render_joined_list_line("Traits", d.get("traits")),
    lambda d: _render_joined_list_line("Visual Novels", d.get("vns"), max_items=3),
]


def _render_basic_field_line(vndb_data: dict[str, Any], field: str, label: str) -> str | None:
    """渲染基础字段行。"""
    value = vndb_data.get(field)
    if not value:
        return None
    return f"- **{label}**: {value}"


def _render_joined_list_line(
    label: str,
    values: list[str] | None,
    max_items: int | None = None,
) -> str | None:
    """渲染列表字段行。"""
    if not values:
        return None
    render_values = values[:max_items] if max_items is not None else values
    return f"- **{label}**: {', '.join(render_values)}"


def _render_measurement_line(label: str, value: Any, unit: str) -> str | None:
    """渲染数值单位字段行。"""
    if not value:
        return None
    return f"- **{label}**: {value}{unit}"


def _render_measurements_line(bust: Any, waist: Any, hips: Any) -> str | None:
    """渲染三围字段行。"""
    if not (bust and waist and hips):
        return None
    return f"- **Measurements**: {bust}-{waist}-{hips}cm"


def _build_vndb_section(vndb_data: dict[str, Any]) -> str:
    """构造 VNDB 信息段落。"""
    lines = [*_VNDB_SECTION_PREFIX_LINES, _VNDB_SECTION_TITLE, ""]

    for field, label in _VNDB_FIELD_LABELS:
        line = _render_basic_field_line(vndb_data, field, label)
        if line:
            lines.append(line)

    for renderer in _VNDB_OPTIONAL_RENDERERS:
        line = renderer(vndb_data)
        if line:
            lines.append(line)

    return "\n".join(lines)


def append_vndb_info_to_skill_md(
    skill_md_path: str,
    vndb_data: dict[str, Any] | None,
) -> str | None:
    """向 SKILL.md 追加 VNDB 信息。

    Args:
        skill_md_path: SKILL.md 路径。
        vndb_data: VNDB 数据。

    Returns:
        str | None: 处理结果消息。

    Raises:
        Exception: 文件写入异常未被内部拦截时向上抛出。
    """
    if not (skill_md_path and os.path.exists(skill_md_path) and vndb_data):
        return None

    try:
        _append_text_to_file(skill_md_path, _build_vndb_section(vndb_data))
        return "Added VNDB info to SKILL.md"
    except Exception as e:
        return f"Warning: Failed to add VNDB info to SKILL.md: {e}"


def create_code_skill_copy(script_dir: str, role_name: str) -> str | None:
    """创建代码版技能目录副本。

    Args:
        script_dir: 技能目录根路径。
        role_name: 角色名。

    Returns:
        str | None: 处理结果消息。

    Raises:
        Exception: 目录复制异常未被内部拦截时向上抛出。
    """
    main_skill_dir = os.path.join(script_dir, f"{role_name}-skill-main")
    if not os.path.exists(main_skill_dir):
        return None

    code_skill_dir = os.path.join(script_dir, f"{role_name}-skill-code")
    try:
        _reset_code_skill_dir(main_skill_dir, code_skill_dir)
        _remove_limit_file(code_skill_dir)
        return f"Created {role_name}-skill-code (without limit.md)"
    except Exception as e:
        return f"Warning: Failed to create -code version: {e}"


def _reset_code_skill_dir(main_skill_dir: str, code_skill_dir: str) -> None:
    """重建代码版技能目录。"""
    import shutil

    if os.path.exists(code_skill_dir):
        shutil.rmtree(code_skill_dir)
    shutil.copytree(main_skill_dir, code_skill_dir)


def _remove_limit_file(code_skill_dir: str) -> None:
    """删除代码版技能目录中的 limit.md。"""
    limit_file = os.path.join(code_skill_dir, "limit.md")
    if os.path.exists(limit_file):
        os.remove(limit_file)


def _append_text_to_file(path: str, text: str) -> None:
    """向文件末尾追加文本。"""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content + text)
