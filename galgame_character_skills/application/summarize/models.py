"""summarize 切片执行数据模型。"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SliceTask:
    """切片任务模型。"""

    slice_index: int
    slice_content: str
    role_name: str
    instruction: str
    output_file_path: str
    config: dict
    output_language: str
    mode: str
    vndb_data: object
    checkpoint_id: str | None


@dataclass
class SliceExecutionResult:
    """单个切片执行结果模型。"""

    index: int
    success: bool = False
    summary: str | None = None
    tool_results: list = None
    output_path: str = ""
    character_analysis: dict | None = None
    lorebook_entries: list = None
    restored: bool = False

    def __post_init__(self):
        if self.tool_results is None:
            self.tool_results = []
        if self.lorebook_entries is None:
            self.lorebook_entries = []

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


@dataclass
class SummarizeExecutionAggregate:
    """summarize 并发执行聚合结果。"""

    summaries: list = None
    errors: list = None
    all_results: list = None
    all_character_analyses: list = None
    all_lorebook_entries: list = None

    def __post_init__(self):
        if self.summaries is None:
            self.summaries = []
        if self.errors is None:
            self.errors = []
        if self.all_results is None:
            self.all_results = []
        if self.all_character_analyses is None:
            self.all_character_analyses = []
        if self.all_lorebook_entries is None:
            self.all_lorebook_entries = []


def to_slice_task(args: SliceTask | tuple[Any, ...]) -> SliceTask:
    """将切片参数归一化为任务对象。"""
    if isinstance(args, SliceTask):
        return args

    (
        slice_index,
        slice_content,
        role_name,
        instruction,
        output_file_path,
        config,
        output_language,
        mode,
        vndb_data,
        checkpoint_id,
    ) = args
    return SliceTask(
        slice_index=slice_index,
        slice_content=slice_content,
        role_name=role_name,
        instruction=instruction,
        output_file_path=output_file_path,
        config=config,
        output_language=output_language,
        mode=mode,
        vndb_data=vndb_data,
        checkpoint_id=checkpoint_id,
    )


__all__ = [
    "SliceTask",
    "SliceExecutionResult",
    "SummarizeExecutionAggregate",
    "to_slice_task",
]
