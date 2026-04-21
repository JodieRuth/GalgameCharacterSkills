"""技能上下文构建模块，负责从 summary 中提取重点并拼装生成上下文。"""

import os


def extract_summary_highlights(content, max_chars=5000):
    lines = content.splitlines()
    selected = []
    current_len = 0

    def add_line(line):
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


def extract_key_sections(content, max_chars=8000):
    key_heading_keywords = (
        "核心", "关键", "关系", "经历", "事件", "人格", "语言", "行为",
        "情绪", "设定", "背景", "成长", "矛盾", "identity", "relationship",
        "speech", "behavior", "event", "background", "persona", "emotion"
    )
    lines = content.splitlines()
    sections = []
    current_heading = None
    current_lines = []

    def flush_section():
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


def build_full_skill_generation_context(summary_files):
    sections = []
    for file_path in summary_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        sections.append(f"=== {os.path.basename(file_path)} ===\n{content}")
    return "\n\n".join(sections)


def head_tail_weighted_order(items):
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


def build_prioritized_skill_generation_context(summary_files, target_total_chars=200000):
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

    def add_section(name, body, suffix=None):
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
