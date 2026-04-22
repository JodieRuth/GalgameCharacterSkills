"""文本归纳用例模块，负责请求准备、任务编排与结果收尾。"""

import os
from typing import Any

from ...checkpoint import load_resumable_checkpoint
from ..app_container import TaskRuntimeDependencies
from ..shared.task_prepared import PreparedSummarizeTask
from ..shared.task_result_factory import ok_task_result, fail_task_result
from ..shared.task_state import SummarizeResumeState
from ..shared.task_prepare_context import (
    build_basic_prepared_builder,
    build_on_resumed_logger,
    prepare_task_context,
)
from .checkpoint import (
    build_summarize_resumed_handler,
)
from .slice_executor import (
    SliceTask,
    SummarizeExecutionAggregate,
    execute_slice_tasks,
)
from ...config.request_config import build_llm_config
from ...utils.input_normalization import extract_file_paths
from ...domain import SummarizeRequest, fail_result, TASK_TYPE_SUMMARIZE


_build_prepared_summarize_task = build_basic_prepared_builder(PreparedSummarizeTask)
_log_summarize_resumed = build_on_resumed_logger(
    lambda _request_data, checkpoint_data, _runtime: (
        f"Resuming summarize: "
        f"{len(set(checkpoint_data.state.checkpoint.get('progress', {}).get('completed_items', [])))}/"
        f"{checkpoint_data.state.checkpoint.get('progress', {}).get('total_steps', '?')} "
        "slices already done"
    )
)

def _from_summarize_payload(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> SummarizeRequest:
    """从原始载荷构造归纳请求。

    Args:
        data: 原始请求数据。
        runtime: 任务运行时依赖。

    Returns:
        SummarizeRequest: 标准化后的归纳请求。

    Raises:
        Exception: 请求解析失败时向上抛出。
    """
    return SummarizeRequest.from_payload(data, runtime.clean_vndb_data, extract_file_paths)


def _validate_summarize_before_checkpoint(
    request_data: SummarizeRequest,
    _data: dict[str, Any],
    _runtime: TaskRuntimeDependencies,
) -> dict[str, Any] | None:
    """执行 checkpoint 前校验。

    Args:
        request_data: 归纳请求。
        _data: 原始请求数据。
        _runtime: 任务运行时依赖。

    Returns:
        dict[str, Any] | None: 校验失败结果或空值。

    Raises:
        Exception: 校验流程失败时向上抛出。
    """
    if not request_data.role_name:
        return fail_result('请输入角色名称')
    if not request_data.resume_checkpoint_id and not request_data.file_paths:
        return fail_result('请先选择文件')
    return None


def _validate_summarize_after_checkpoint(
    request_data: SummarizeRequest,
    _data: dict[str, Any],
    _runtime: TaskRuntimeDependencies,
    _checkpoint_data: Any,
) -> dict[str, Any] | None:
    """执行 checkpoint 后校验。

    Args:
        request_data: 归纳请求。
        _data: 原始请求数据。
        _runtime: 任务运行时依赖。
        _checkpoint_data: checkpoint 预处理结果。

    Returns:
        dict[str, Any] | None: 校验失败结果或空值。

    Raises:
        Exception: 校验流程失败时向上抛出。
    """
    if not request_data.file_paths:
        return fail_result('请先选择文件')
    return None


_on_summarize_resumed = build_summarize_resumed_handler(
    _log_summarize_resumed,
)


def _prepare_summarize_request(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
) -> tuple[PreparedSummarizeTask | None, dict[str, Any] | None]:
    """准备归纳请求。

    Args:
        data: 原始请求数据。
        runtime: 任务运行时依赖。

    Returns:
        tuple[PreparedSummarizeTask | None, dict[str, Any] | None]: prepared 对象和错误结果。

    Raises:
        Exception: 请求预处理失败时向上抛出。
    """
    return prepare_task_context(
        data=data,
        runtime=runtime,
        from_payload=_from_summarize_payload,
        config_builder=build_llm_config,
        checkpoint_task_type=TASK_TYPE_SUMMARIZE,
        load_resume_state=lambda _gateway, _checkpoint_id, checkpoint: SummarizeResumeState(checkpoint=checkpoint),
        build_initial_state=lambda: SummarizeResumeState(checkpoint={}),
        load_resumable_checkpoint_fn=load_resumable_checkpoint,
        build_prepared=_build_prepared_summarize_task,
        validate_before_checkpoint=_validate_summarize_before_checkpoint,
        validate_after_checkpoint=_validate_summarize_after_checkpoint,
        on_resumed=_on_summarize_resumed,
    )


def _build_summary_dir(
    file_paths: list[str],
    role_name: str,
    runtime: TaskRuntimeDependencies,
) -> str:
    """构造 summary 输出目录。

    Args:
        file_paths: 输入文件路径列表。
        role_name: 角色名。
        runtime: 任务运行时依赖。

    Returns:
        str: summary 输出目录路径。

    Raises:
        Exception: 目录路径构造失败时向上抛出。
    """
    summaries_root = runtime.get_workspace_summaries_dir()
    os.makedirs(summaries_root, exist_ok=True)

    if len(file_paths) == 1:
        file_name = os.path.basename(file_paths[0])
        name, _ = os.path.splitext(file_name)
        return os.path.join(summaries_root, f"{name}_summaries")

    name = os.path.basename(file_paths[0])
    name = os.path.splitext(name)[0]
    return os.path.join(summaries_root, f"{name}_merged_summaries")


def _build_slice_tasks(
    current_slices: list[str],
    summary_dir: str,
    request_data: SummarizeRequest,
    config: dict[str, Any],
    checkpoint_id: str,
) -> list[SliceTask]:
    """构造切片任务列表。

    Args:
        current_slices: 当前切片内容列表。
        summary_dir: summary 输出目录。
        request_data: 归纳请求。
        config: LLM 配置。
        checkpoint_id: checkpoint 标识。

    Returns:
        list[SliceTask]: 切片任务列表。

    Raises:
        Exception: 任务构造失败时向上抛出。
    """
    tasks = []
    for i, slice_content in enumerate(current_slices):
        if request_data.mode == 'chara_card':
            output_file_path = os.path.join(summary_dir, f"slice_{i+1:03d}_{request_data.role_name}.json")
        else:
            output_file_path = os.path.join(summary_dir, f"slice_{i+1:03d}_{request_data.role_name}.md")
        tasks.append(
            SliceTask(
                slice_index=i,
                slice_content=slice_content,
                role_name=request_data.role_name,
                instruction=request_data.instruction,
                output_file_path=output_file_path,
                config=config,
                output_language=request_data.output_language,
                mode=request_data.mode,
                vndb_data=request_data.vndb_data,
                checkpoint_id=checkpoint_id,
            )
        )
    return tasks


def _execute_slice_tasks(
    tasks: list[SliceTask],
    request_data: SummarizeRequest,
    runtime: TaskRuntimeDependencies,
    request_runtime: Any = None,
) -> SummarizeExecutionAggregate:
    """并发执行切片任务。

    Args:
        tasks: 切片任务列表。
        request_data: 归纳请求。
        runtime: 任务运行时依赖。
        request_runtime: 请求级 LLM 运行时。

    Returns:
        SummarizeExecutionAggregate: 归纳执行汇总结果。

    Raises:
        Exception: 切片执行器异常未被内部拦截时向上抛出。
    """
    return execute_slice_tasks(tasks, request_data, runtime, request_runtime=request_runtime)


def _finalize_summarize_result(
    request_data: SummarizeRequest,
    current_slices: list[str],
    summary_dir: str,
    execution: SummarizeExecutionAggregate,
    checkpoint_id: str,
    runtime: TaskRuntimeDependencies,
) -> dict[str, Any]:
    """完成归纳任务结果收尾。

    Args:
        request_data: 归纳请求。
        current_slices: 当前切片内容列表。
        summary_dir: summary 输出目录。
        execution: 归纳执行汇总结果。
        checkpoint_id: checkpoint 标识。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: 统一任务结果。

    Raises:
        Exception: 结果写入或 checkpoint 更新失败时向上抛出。
    """
    if request_data.mode == 'chara_card':
        analysis_summary_path = os.path.join(summary_dir, f"{request_data.role_name}_analysis_summary.json")
        runtime.storage_gateway.write_json(
            analysis_summary_path,
            {
                'character_analyses': execution.all_character_analyses,
                'lorebook_entries': execution.all_lorebook_entries,
            },
            ensure_ascii=False,
            indent=2,
        )

    if execution.errors and len(execution.summaries) == 0:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, f"{len(execution.errors)} 个切片全部失败")
        return fail_task_result(
            f"归纳失败，{len(execution.errors)} 个切片失败",
            slice_count=len(current_slices),
            errors=execution.errors,
            results=execution.all_results,
            checkpoint_id=checkpoint_id,
            can_resume=True,
        )

    if execution.errors:
        runtime.checkpoint_gateway.mark_failed(checkpoint_id, f"{len(execution.errors)} 个切片失败，可恢复继续处理")
        return ok_task_result(
            message=f"归纳部分完成，{len(execution.errors)} 个切片失败，可通过任务列表继续",
            slice_count=len(current_slices),
            errors=execution.errors,
            results=execution.all_results,
            checkpoint_id=checkpoint_id,
            can_resume=True,
        )

    runtime.checkpoint_gateway.mark_completed(checkpoint_id)
    return ok_task_result(
        message='归纳完成',
        slice_count=len(current_slices),
        results=execution.all_results,
        checkpoint_id=checkpoint_id,
    )


def run_summarize_task(data: dict[str, Any], runtime: TaskRuntimeDependencies) -> dict[str, Any]:
    """执行文本归纳任务。

    Args:
        data: 任务请求数据，支持新建和恢复执行。
        runtime: 任务运行时依赖。

    Returns:
        dict[str, Any]: 统一任务结果，包含成功数据或失败信息。

    Raises:
        Exception: 底层文件、存储或模型调用未被内部拦截时向上抛出。
    """
    prepared, error = _prepare_summarize_request(data, runtime)
    if error:
        return error

    request_data = prepared.request_data
    config = prepared.config
    checkpoint_id = prepared.checkpoint_id

    current_slices = runtime.file_processor.slice_multiple_files(request_data.file_paths, request_data.slice_size_k)
    llm_request_runtime = runtime.llm_gateway.create_request_runtime(len(current_slices))

    summary_dir = _build_summary_dir(request_data.file_paths, request_data.role_name, runtime)
    runtime.storage_gateway.makedirs(summary_dir, exist_ok=True)

    if not request_data.resume_checkpoint_id:
        runtime.checkpoint_gateway.update_progress(
            checkpoint_id,
            total_steps=len(current_slices),
            pending_items=list(range(len(current_slices)))
        )

    tasks = _build_slice_tasks(current_slices, summary_dir, request_data, config, checkpoint_id)
    execution = _execute_slice_tasks(tasks, request_data, runtime, request_runtime=llm_request_runtime)

    return _finalize_summarize_result(
        request_data=request_data,
        current_slices=current_slices,
        summary_dir=summary_dir,
        execution=execution,
        checkpoint_id=checkpoint_id,
        runtime=runtime,
    )
