import os


def append_vndb_info_to_skill_md(skill_md_path, vndb_data):
    if not (skill_md_path and os.path.exists(skill_md_path) and vndb_data):
        return None

    try:
        with open(skill_md_path, 'r', encoding='utf-8') as f:
            skill_content = f.read()

        vndb_section = "\n\n---\n\n## VNDB Character Information\n\n"
        if vndb_data.get('name'):
            vndb_section += f"- **Name**: {vndb_data['name']}\n"
        if vndb_data.get('original_name'):
            vndb_section += f"- **Original Name**: {vndb_data['original_name']}\n"
        if vndb_data.get('aliases'):
            vndb_section += f"- **Aliases**: {', '.join(vndb_data['aliases'])}\n"
        if vndb_data.get('description'):
            vndb_section += f"- **Description**: {vndb_data['description']}\n"
        if vndb_data.get('age'):
            vndb_section += f"- **Age**: {vndb_data['age']}\n"
        if vndb_data.get('birthday'):
            vndb_section += f"- **Birthday**: {vndb_data['birthday']}\n"
        if vndb_data.get('blood_type'):
            vndb_section += f"- **Blood Type**: {vndb_data['blood_type']}\n"
        if vndb_data.get('height'):
            vndb_section += f"- **Height**: {vndb_data['height']}cm\n"
        if vndb_data.get('weight'):
            vndb_section += f"- **Weight**: {vndb_data['weight']}kg\n"
        if vndb_data.get('bust') and vndb_data.get('waist') and vndb_data.get('hips'):
            vndb_section += f"- **Measurements**: {vndb_data['bust']}-{vndb_data['waist']}-{vndb_data['hips']}cm\n"
        if vndb_data.get('traits'):
            vndb_section += f"- **Traits**: {', '.join(vndb_data['traits'])}\n"
        if vndb_data.get('vns'):
            games = vndb_data['vns'][:3]
            vndb_section += f"- **Visual Novels**: {', '.join(games)}\n"

        skill_content += vndb_section
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
