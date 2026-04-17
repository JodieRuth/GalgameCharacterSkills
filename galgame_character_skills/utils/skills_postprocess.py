import os


_VNDB_FIELD_LABELS = [
    ("name", "Name"),
    ("original_name", "Original Name"),
    ("description", "Description"),
    ("age", "Age"),
    ("birthday", "Birthday"),
    ("blood_type", "Blood Type"),
]


def _build_vndb_section(vndb_data):
    lines = ["", "", "---", "", "## VNDB Character Information", ""]

    for field, label in _VNDB_FIELD_LABELS:
        value = vndb_data.get(field)
        if value:
            lines.append(f"- **{label}**: {value}")

    aliases = vndb_data.get("aliases")
    if aliases:
        lines.append(f"- **Aliases**: {', '.join(aliases)}")

    height = vndb_data.get("height")
    if height:
        lines.append(f"- **Height**: {height}cm")

    weight = vndb_data.get("weight")
    if weight:
        lines.append(f"- **Weight**: {weight}kg")

    if vndb_data.get("bust") and vndb_data.get("waist") and vndb_data.get("hips"):
        lines.append(f"- **Measurements**: {vndb_data['bust']}-{vndb_data['waist']}-{vndb_data['hips']}cm")

    traits = vndb_data.get("traits")
    if traits:
        lines.append(f"- **Traits**: {', '.join(traits)}")

    games = vndb_data.get("vns")
    if games:
        lines.append(f"- **Visual Novels**: {', '.join(games[:3])}")

    return "\n".join(lines)


def append_vndb_info_to_skill_md(skill_md_path, vndb_data):
    if not (skill_md_path and os.path.exists(skill_md_path) and vndb_data):
        return None

    try:
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            skill_content = f.read()

        skill_content += _build_vndb_section(vndb_data)
        with open(skill_md_path, 'w', encoding='utf-8') as f:
            f.write(skill_content)
        return "Added VNDB info to SKILL.md"
    except Exception as e:
        return f"Warning: Failed to add VNDB info to SKILL.md: {e}"


def create_code_skill_copy(script_dir, role_name):
    main_skill_dir = os.path.join(script_dir, f"{role_name}-skill-main")
    code_skill_dir = os.path.join(script_dir, f"{role_name}-skill-code")
    if not os.path.exists(main_skill_dir):
        return None

    try:
        import shutil
        if os.path.exists(code_skill_dir):
            shutil.rmtree(code_skill_dir)
        shutil.copytree(main_skill_dir, code_skill_dir)
        limit_file = os.path.join(code_skill_dir, "limit.md")
        if os.path.exists(limit_file):
            os.remove(limit_file)
        return f"Created {role_name}-skill-code (without limit.md)"
    except Exception as e:
        return f"Warning: Failed to create -code version: {e}"
