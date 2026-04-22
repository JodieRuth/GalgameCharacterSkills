"""Prompt 模板子模块，集中导出各任务提示词构造函数。"""

from .character_card import build_compress_content_payload
from .skills import build_generate_skills_folder_init_payload
from .summarize import (
    build_summarize_chara_card_payload,
    build_summarize_content_payload,
)

__all__ = [
    "build_summarize_content_payload",
    "build_summarize_chara_card_payload",
    "build_generate_skills_folder_init_payload",
    "build_compress_content_payload",
]
