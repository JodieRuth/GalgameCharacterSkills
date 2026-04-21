"""Summary 文件发现模块，负责按角色和模式定位归纳产物。"""

import os


def _iter_summary_dirs(base_dir):
    for root, dirs, files in os.walk(base_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                yield os.path.join(root, dir_name)


def discover_summary_roles(base_dir):
    skills_roles = set()
    chara_card_roles = set()

    for summaries_dir in _iter_summary_dirs(base_dir):
        try:
            dir_files = os.listdir(summaries_dir)
            for filename in dir_files:
                if filename.endswith('.md'):
                    parts = filename.replace('.md', '').split('_')
                    if len(parts) >= 3 and parts[0] == 'slice':
                        role_name = '_'.join(parts[2:])
                        if role_name:
                            skills_roles.add(role_name)
                elif filename.endswith('_analysis_summary.json'):
                    role_name = filename.replace('_analysis_summary.json', '')
                    if role_name:
                        chara_card_roles.add(role_name)
        except Exception:
            pass

    for summaries_dir in _iter_summary_dirs(base_dir):
        try:
            dir_files = os.listdir(summaries_dir)
            for filename in dir_files:
                if filename.startswith('slice_') and filename.endswith('.json'):
                    parts = filename.replace('.json', '').split('_')
                    if len(parts) >= 3:
                        role_name = '_'.join(parts[2:])
                        if role_name:
                            chara_card_roles.add(role_name)
        except Exception:
            pass

    return {
        'roles': sorted(list(skills_roles | chara_card_roles)),
        'skills_roles': sorted(list(skills_roles)),
        'chara_card_roles': sorted(list(chara_card_roles))
    }


def find_summary_files_for_role(base_dir, role_name, mode='skills'):
    matching_files = []
    for summaries_dir in _iter_summary_dirs(base_dir):
        try:
            for filename in sorted(os.listdir(summaries_dir)):
                if mode == 'chara_card':
                    if filename.endswith('.json') and f'_{role_name}' in filename:
                        matching_files.append(os.path.join(summaries_dir, filename))
                else:
                    if filename.endswith('.md') and f'_{role_name}.md' in filename:
                        matching_files.append(os.path.join(summaries_dir, filename))
        except Exception:
            pass
    return sorted(matching_files)


def find_role_summary_markdown_files(base_dir, role_name):
    summary_files = []
    for summaries_dir in _iter_summary_dirs(base_dir):
        try:
            for filename in sorted(os.listdir(summaries_dir)):
                if filename.endswith('.md') and f'_{role_name}.md' in filename:
                    summary_files.append(os.path.join(summaries_dir, filename))
        except Exception:
            pass
    return summary_files


def find_role_analysis_summary_file(base_dir, role_name):
    for summaries_dir in _iter_summary_dirs(base_dir):
        summary_path = os.path.join(summaries_dir, f"{role_name}_analysis_summary.json")
        if os.path.exists(summary_path):
            return summary_path
    return None
