"""技能上下文构建模块，负责从 summary 中提取重点并拼装生成上下文。"""

import os
from typing import Any


def extract_summary_highlights(content: str, max_chars: int = 5000) -> str:
    """提取 summary 的高密度上下文片段。

    Args:
        content: summary 文本。
        max_chars: 最大字符数。

    Returns:
        str: 压缩后的上下文文本。

    Raises:
        Exception: 文本处理失败时向上抛出。
    """
    lines = content.splitlines()
    selected = []
    current_len = 0

    def add_line(line: str) -> None:
        nonlocal current_len
        if not line:
            return
        extra = len(line) + 1
        if current_len + extra > max_chars:
            return
        selected.append(line)
        current_len += extra

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('#', '##', '###', '####', '-', '*', '>', '|')):
            add_line(stripped)

    if current_len < max_chars:
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(('#', '##', '###', '####', '-', '*', '>', '|')):
                continue
            add_line(stripped[:300])
            if current_len >= max_chars:
                break

    if not selected:
        return content[:max_chars]

    result = "\n".join(selected)
    if len(result) < len(content):
        result += "\n[Truncated for context budget]"
    return result


def extract_key_sections(content: str, max_chars: int = 8000) -> str:
    """提取 summary 中的关键章节。

    Args:
        content: summary 文本。
        max_chars: 最大字符数。

    Returns:
        str: 关键章节文本。

    Raises:
        Exception: 文本处理失败时向上抛出。
    """
    key_heading_keywords = (
        "核心", "关键", "关系", "经历", "事件", "人格", "语言", "行为",
        "情绪", "设定", "背景", "成长", "矛盾", "identity", "relationship",
        "speech", "behavior", "event", "background", "persona", "emotion"
    )
    lines = content.splitlines()
    sections = []
    current_heading = None
    current_lines = []

    def flush_section() -> None:
        if current_heading is not None and current_lines:
            sections.append((current_heading, "\n".join(current_lines).strip()))

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            flush_section()
            current_heading = stripped
            current_lines = [stripped]
        elif current_heading is not None:
            current_lines.append(line)

    flush_section()

    selected = []
    used = 0
    for heading, block in sections:
        if not any(keyword.lower() in heading.lower() for keyword in key_heading_keywords):
            continue
        candidate = block.strip()
        if not candidate:
            continue
        extra = len(candidate) + 2
        if used + extra > max_chars:
            remaining = max_chars - used
            if remaining > 200:
                selected.append(candidate[:remaining].rstrip() + "\n[Truncated key section]")
            break
        selected.append(candidate)
        used += extra

    if not selected:
        return ""
    return "\n\n".join(selected)


def build_full_skill_generation_context(summary_files: list[str]) -> str:
    """构造完整技能生成上下文。

    Args:
        summary_files: summary 文件路径列表。

    Returns:
        str: 拼接后的完整上下文。

    Raises:
        Exception: 文件读取异常未被内部拦截时向上抛出。
    """
    sections = []
    for file_path in summary_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        sections.append(f"=== {os.path.basename(file_path)} ===\n{content}")
    return "\n\n".join(sections)


def head_tail_weighted_order(items: list[Any]) -> list[Any]:
    """按头尾加权顺序重排列表。

    Args:
        items: 原始列表。

    Returns:
        list[Any]: 重排后的列表。

    Raises:
        Exception: 排序失败时向上抛出。
    """
    ordered = []
    left = 0
    right = len(items) - 1
    pattern = ("head", "tail", "tail")
    step = 0

    while left <= right:
        direction = pattern[step % len(pattern)]
        if direction == "head":
            ordered.append(items[left])
            left += 1
        else:
            ordered.append(items[right])
            right -= 1
        step += 1

    return ordered


def build_prioritized_skill_generation_context(
    summary_files: list[str],
    target_total_chars: int = 200000,
) -> str:
    """构造优先级压缩后的技能生成上下文。

    Args:
        summary_files: summary 文件路径列表。
        target_total_chars: 目标最大字符数。

    Returns:
        str: 压缩后的上下文文本。

    Raises:
        Exception: 文件读取或上下文构造异常未被内部拦截时向上抛出。
    """
    if not summary_files:
        return ""

    file_infos = []
    for file_path in summary_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            file_infos.append({
                "path": file_path,
                "name": os.path.basename(file_path),
                "content": content,
            })
        except Exception:
            continue

    if not file_infos:
        return ""
    sections = []
    used = 0

    def add_section(name: str, body: str, suffix: str | None = None) -> bool:
        nonlocal used
        if not body:
            return False
        label = f"=== {name}"
        if suffix:
            label += f" [{suffix}]"
        label += " ===\n"
        candidate = label + body
        extra = len(candidate) + 2
        if used + extra > target_total_chars:
            remaining = target_total_chars - used
            if remaining <= len(label) + 200:
                return False
            body_budget = remaining - len(label)
            candidate = label + body[:body_budget].rstrip() + "\n[Truncated for context budget]"
            extra = len(candidate) + 2
        sections.append(candidate)
        used += extra
        return used < target_total_chars

    prioritized_infos = head_tail_weighted_order(file_infos)
    full_preserve_count = min(3, len(prioritized_infos))

    for item in prioritized_infos[:full_preserve_count]:
        if not add_section(item["name"], item["content"], suffix="full head-tail weighted"):
            return "\n\n".join(sections)

    for item in prioritized_infos[full_preserve_count:]:
        key_sections = extract_key_sections(item["content"], max_chars=12000)
        if key_sections:
            if not add_section(item["name"], key_sections, suffix="key sections"):
                return "\n\n".join(sections)

    for item in prioritized_infos[full_preserve_count:]:
        if used >= target_total_chars:
            break
        summary_budget = min(8000, max(2500, (target_total_chars - used) // max(1, len(file_infos))))
        compact = extract_summary_highlights(item["content"], max_chars=summary_budget)
        add_section(item["name"], compact, suffix="compressed")

    return "\n\n".join(sections)
