"""技能产物后处理模块，负责追加 VNDB 信息并同步生成代码版技能目录。"""

import os

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


def _render_basic_field_line(vndb_data, field, label):
    value = vndb_data.get(field)
    if not value:
        return None
    return f"- **{label}**: {value}"


def _render_joined_list_line(label, values, max_items=None):
    if not values:
        return None
    render_values = values[:max_items] if max_items is not None else values
    return f"- **{label}**: {', '.join(render_values)}"


def _render_measurement_line(label, value, unit):
    if not value:
        return None
    return f"- **{label}**: {value}{unit}"


def _render_measurements_line(bust, waist, hips):
    if not (bust and waist and hips):
        return None
    return f"- **Measurements**: {bust}-{waist}-{hips}cm"


def _build_vndb_section(vndb_data):
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


def append_vndb_info_to_skill_md(skill_md_path, vndb_data):
    if not (skill_md_path and os.path.exists(skill_md_path) and vndb_data):
        return None

    try:
        _append_text_to_file(skill_md_path, _build_vndb_section(vndb_data))
        return "Added VNDB info to SKILL.md"
    except Exception as e:
        return f"Warning: Failed to add VNDB info to SKILL.md: {e}"


def create_code_skill_copy(script_dir, role_name):
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


def _reset_code_skill_dir(main_skill_dir, code_skill_dir):
    import shutil

    if os.path.exists(code_skill_dir):
        shutil.rmtree(code_skill_dir)
    shutil.copytree(main_skill_dir, code_skill_dir)


def _remove_limit_file(code_skill_dir):
    limit_file = os.path.join(code_skill_dir, "limit.md")
    if os.path.exists(limit_file):
        os.remove(limit_file)


def _append_text_to_file(path, text):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content + text)
