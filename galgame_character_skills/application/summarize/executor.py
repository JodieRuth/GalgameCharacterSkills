"""summarize 并发执行调度模块。"""

from concurrent.futures import as_completed
from typing import Any

from ..app_container import TaskRuntimeDependencies
from .models import SliceTask, SummarizeExecutionAggregate
from .slice_worker import process_single_slice


def execute_slice_tasks(
    tasks: list[SliceTask],
    request_data: Any,
    runtime: TaskRuntimeDependencies,
    request_runtime: Any = None,
) -> SummarizeExecutionAggregate:
    """并发执行切片任务。"""
    execution = SummarizeExecutionAggregate()

    with runtime.executor_gateway.create(max_workers=request_data.concurrency) as executor:
        future_to_task = {
            executor.submit(
                process_single_slice,
                task,
                runtime.checkpoint_gateway,
                runtime.llm_gateway,
                runtime.tool_gateway,
                runtime.storage_gateway,
                request_runtime,
                runtime.log,
            ): task
            for task in tasks
        }

        for future in as_completed(future_to_task):
            try:
                result = future.result()
                if result.success:
                    execution.summaries.append(result.summary)
                    execution.all_results.extend(result.tool_results)
                    if result.character_analysis:
                        execution.all_character_analyses.append(result.character_analysis)
                    if result.lorebook_entries:
                        execution.all_lorebook_entries.append(result.lorebook_entries)
                else:
                    execution.errors.append(f"切片 {result.index + 1} 处理失败")
            except Exception as exc:
                task = future_to_task[future]
                execution.errors.append(f"切片 {task.slice_index + 1} 处理异常: {str(exc)}")

    return execution


__all__ = ["execute_slice_tasks"]
