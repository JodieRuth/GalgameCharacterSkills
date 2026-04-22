"""文本归纳用例模块。"""

from .checkpoint import (
    build_checkpoint_slice_content,
    build_summarize_resumed_handler,
    persist_slice_checkpoint_if_needed,
    sanitize_resume_progress,
)
from .service import run_summarize_task
from .slice_executor import (
    SliceExecutionResult,
    SliceTask,
    SummarizeExecutionAggregate,
    execute_slice_tasks,
    extract_write_file_content,
    finalize_skills_slice_result,
    process_single_slice,
    to_slice_task,
)

__all__ = [
    "SliceExecutionResult",
    "SliceTask",
    "SummarizeExecutionAggregate",
    "build_checkpoint_slice_content",
    "build_summarize_resumed_handler",
    "execute_slice_tasks",
    "extract_write_file_content",
    "finalize_skills_slice_result",
    "persist_slice_checkpoint_if_needed",
    "process_single_slice",
    "run_summarize_task",
    "sanitize_resume_progress",
    "to_slice_task",
]
