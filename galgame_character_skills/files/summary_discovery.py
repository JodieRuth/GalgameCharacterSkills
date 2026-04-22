"""Summary 文件发现模块，负责按角色和模式定位归纳产物。"""

import os
from collections.abc import Iterator


def _iter_summary_dirs(base_dir: str) -> Iterator[str]:
    """遍历 summary 目录。

    Args:
        base_dir: summary 根目录。

    Returns:
        Iterator[str]: summary 目录路径迭代器。

    Raises:
        Exception: 目录遍历失败时向上抛出。
    """
    for root, dirs, files in os.walk(base_dir):
        for dir_name in dirs:
            if dir_name.endswith('_summaries'):
                yield os.path.join(root, dir_name)


def discover_summary_roles(base_dir: str) -> dict[str, list[str]]:
    """发现已生成 summary 的角色列表。

    Args:
        base_dir: summary 根目录。

    Returns:
        dict[str, list[str]]: 角色分类结果。

    Raises:
        Exception: 目录扫描异常未被内部拦截时向上抛出。
    """
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


def find_summary_files_for_role(
    base_dir: str,
    role_name: str,
    mode: str = 'skills',
) -> list[str]:
    """按角色和模式查找 summary 文件。

    Args:
        base_dir: summary 根目录。
        role_name: 角色名。
        mode: 查找模式。

    Returns:
        list[str]: 匹配到的文件路径列表。

    Raises:
        Exception: 文件扫描异常未被内部拦截时向上抛出。
    """
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


def find_role_summary_markdown_files(base_dir: str, role_name: str) -> list[str]:
    """查找角色的 markdown summary 文件。

    Args:
        base_dir: summary 根目录。
        role_name: 角色名。

    Returns:
        list[str]: markdown summary 文件路径列表。

    Raises:
        Exception: 文件扫描异常未被内部拦截时向上抛出。
    """
    summary_files = []
    for summaries_dir in _iter_summary_dirs(base_dir):
        try:
            for filename in sorted(os.listdir(summaries_dir)):
                if filename.endswith('.md') and f'_{role_name}.md' in filename:
                    summary_files.append(os.path.join(summaries_dir, filename))
        except Exception:
            pass
    return summary_files


def find_role_analysis_summary_file(base_dir: str, role_name: str) -> str | None:
    """查找角色分析汇总文件。

    Args:
        base_dir: summary 根目录。
        role_name: 角色名。

    Returns:
        str | None: 分析汇总文件路径。

    Raises:
        Exception: 文件扫描失败时向上抛出。
    """
    for summaries_dir in _iter_summary_dirs(base_dir):
        summary_path = os.path.join(summaries_dir, f"{role_name}_analysis_summary.json")
        if os.path.exists(summary_path):
            return summary_path
    return None
