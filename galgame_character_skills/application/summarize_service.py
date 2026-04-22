"""文本归纳用例模块，负责切片调度、并发执行、checkpoint 与结果汇总。"""

import json
import os
import time
from concurrent.futures import as_completed
from dataclasses import dataclass
from typing import Any

from ..checkpoint import load_resumable_checkpoint
from .app_container import TaskRuntimeDependencies
from .task_prepared import PreparedSummarizeTask
from .task_result_factory import ok_task_result, fail_task_result
from .task_state import SummarizeResumeState
from .task_prepare_context import (
    build_basic_prepared_builder,
    build_on_resumed_logger,
    chain_on_resumed,
    prepare_task_context,
)
from ..config.request_config import build_llm_config
from ..utils.input_normalization import extract_file_paths
from ..domain import SummarizeRequest, fail_result
from ..workspace import get_workspace_summaries_dir


_build_prepared_summarize_task = build_basic_prepared_builder(PreparedSummarizeTask)
_log_summarize_resumed = build_on_resumed_logger(
    lambda _request_data, checkpoint_data, _runtime: (
        f"Resuming summarize: "
        f"{len(set(checkpoint_data.state.checkpoint.get('progress', {}).get('completed_items', [])))}/"
        f"{checkpoint_data.state.checkpoint.get('progress', {}).get('total_steps', '?')} "
        "slices already done"
    )
)


@dataclass(frozen=True)
class SliceTask:
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


def _to_slice_task(args: SliceTask | tuple[Any, ...]) -> SliceTask:
    """将切片参数归一化为任务对象。

    Args:
        args: 切片任务对象或其元组形式。

    Returns:
        SliceTask: 归一化后的切片任务。

    Raises:
        ValueError: 元组结构不符合预期时抛出。
    """
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


def _build_checkpoint_slice_content(
    mode: str,
    output_file_path: str,
    choice: Any,
    result: SliceExecutionResult,
    storage_gateway: Any,
) -> str:
    """构造切片 checkpoint 内容。

    Args:
        mode: 归纳模式。
        output_file_path: 切片输出路径。
        choice: LLM 返回选择项。
        result: 切片执行结果。
        storage_gateway: 存储网关。

    Returns:
        str: 用于写入 checkpoint 的切片内容。

    Raises:
        Exception: 内容提取失败时向上抛出。
    """
    if mode == 'chara_card':
        return storage_gateway.read_text(output_file_path)

    # Keep checkpoint content aligned with the actual markdown file when present.
    try:
        if storage_gateway.exists(output_file_path):
            return storage_gateway.read_text(output_file_path)
    except Exception:
        pass

    if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
        for tool_call in choice.message.tool_calls:
            if hasattr(tool_call, 'function') and tool_call.function.name == 'write_file':
                args_dict = json.loads(tool_call.function.arguments)
                return args_dict.get('content', '')

    return result['summary'] or ''


def _extract_write_file_content(choice: Any) -> str:
    """提取 write_file 工具中的文本内容。

    Args:
        choice: LLM 返回选择项。

    Returns:
        str: write_file 中的 content 字段。

    Raises:
        Exception: 工具参数解析异常未被内部拦截时向上抛出。
    """
    if not (hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls') and choice.message.tool_calls):
        return ""
    for tool_call in choice.message.tool_calls:
        if hasattr(tool_call, 'function') and tool_call.function.name == 'write_file':
            try:
                args_dict = json.loads(tool_call.function.arguments)
            except Exception:
                return ""
            return args_dict.get('content', '') or ''
    return ""


def _finalize_skills_slice_result(
    result: SliceExecutionResult,
    choice: Any,
    output_file_path: str,
    storage_gateway: Any,
) -> None:
    """完成 skills 模式切片结果落盘。

    Args:
        result: 切片执行结果。
        choice: LLM 返回选择项。
        output_file_path: 切片输出路径。
        storage_gateway: 存储网关。

    Returns:
        None

    Raises:
        Exception: 文件写入失败时向上抛出。
    """
    content_from_tool = _extract_write_file_content(choice)
    content = content_from_tool or (result.summary or "")
    if not content.strip():
        result.success = False
        result.summary = None
        result.tool_results.append("Empty summary content")
        return

    # If tool call did not write file, persist content from plain-text response.
    if not content_from_tool:
        storage_gateway.write_text(output_file_path, content)
        result.summary = content

    # Treat disk write as the source of truth for success in skills mode.
    if not storage_gateway.exists(output_file_path):
        result.success = False
        result.summary = None
        result.tool_results.append("Summary file was not saved")


def _persist_slice_checkpoint_if_needed(
    checkpoint_id: str | None,
    slice_index: int,
    mode: str,
    output_file_path: str,
    choice: Any,
    result: SliceExecutionResult,
    ckpt_manager: Any,
    storage_gateway: Any,
) -> None:
    """按需持久化切片 checkpoint。

    Args:
        checkpoint_id: checkpoint 标识。
        slice_index: 切片索引。
        mode: 归纳模式。
        output_file_path: 切片输出路径。
        choice: LLM 返回选择项。
        result: 切片执行结果。
        ckpt_manager: checkpoint 网关。
        storage_gateway: 存储网关。

    Returns:
        None

    Raises:
        Exception: checkpoint 保存异常未被内部拦截时向上抛出。
    """
    if not (result.success and checkpoint_id):
        return

    try:
        ckpt_content = _build_checkpoint_slice_content(
            mode=mode,
            output_file_path=output_file_path,
            choice=choice,
            result=result,
            storage_gateway=storage_gateway,
        )
        ckpt_manager.save_slice_result(checkpoint_id, slice_index, ckpt_content, 'completed')
        ckpt_manager.mark_slice_completed(checkpoint_id, slice_index)
    except Exception as e:
        print(f"Failed to save slice {slice_index} result: {e}")


def _process_single_slice(
    args: SliceTask | tuple[Any, ...],
    ckpt_manager: Any,
    llm_gateway: Any,
    tool_gateway: Any,
    storage_gateway: Any,
) -> SliceExecutionResult:
    """执行单个切片归纳。

    Args:
        args: 切片任务对象或其元组形式。
        ckpt_manager: checkpoint 网关。
        llm_gateway: LLM 网关。
        tool_gateway: 工具网关。
        storage_gateway: 存储网关。

    Returns:
        SliceExecutionResult: 切片执行结果。

    Raises:
        Exception: 切片处理异常未被内部拦截时向上抛出。
    """
    task = _to_slice_task(args)
    slice_index = task.slice_index
    output_file_path = task.output_file_path
    mode = task.mode
    checkpoint_id = task.checkpoint_id
    llm_client = llm_gateway.create_client(task.config)

    if checkpoint_id:
        existing = ckpt_manager.get_slice_result(checkpoint_id, slice_index)
        if existing:
            print(f"Slice {slice_index} already completed, skipping")
            result = SliceExecutionResult(
                index=slice_index,
                success=True,
                summary=f"Slice {slice_index + 1} restored from checkpoint",
                output_path=output_file_path,
                restored=True,
            )
            if mode == 'chara_card':
                try:
                    if not storage_gateway.exists(output_file_path):
                        return result
                    parsed = storage_gateway.read_json(output_file_path)
                    result.character_analysis = parsed.get('character_analysis', {})
                    result.lorebook_entries = parsed.get('lorebook_entries', [])
                except Exception:
                    pass
            else:
                try:
                    if not storage_gateway.exists(output_file_path):
                        return result
                    content = storage_gateway.read_text(output_file_path)
                    result.summary = content[:200] + "..." if len(content) > 200 else content
                except Exception:
                    pass
            return result

    time.sleep(0.5 * slice_index)

    if mode == 'chara_card':
        response = llm_client.summarize_content_for_chara_card(
            task.slice_content,
            task.role_name,
            task.instruction,
            output_file_path,
            task.output_language,
            task.vndb_data,
        )
    else:
        response = llm_client.summarize_content(
            task.slice_content,
            task.role_name,
            task.instruction,
            output_file_path,
            task.output_language,
            task.vndb_data,
        )

    result = SliceExecutionResult(index=slice_index, output_path=output_file_path)
    choice = None

    if response and hasattr(response, 'choices') and response.choices:
        choice = response.choices[0]

        if mode == 'chara_card':
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    tool_result = tool_gateway.handle_tool_call(tool_call)
                    result.tool_results.append(tool_result)
                result.success = True
                result.summary = f"Slice {slice_index + 1} saved to {output_file_path}"

                try:
                    parsed = storage_gateway.read_json(output_file_path)
                    result.character_analysis = parsed.get('character_analysis', {})
                    result.lorebook_entries = parsed.get('lorebook_entries', [])
                except Exception as e:
                    result.tool_results.append(f"Warning: Failed to read saved file: {e}")

            elif hasattr(choice, 'message') and choice.message.content:
                content = choice.message.content
                parsed = tool_gateway.parse_llm_json_response(content)
                if parsed:
                    result.character_analysis = parsed.get('character_analysis', {})
                    result.lorebook_entries = parsed.get('lorebook_entries', [])
                    result.success = True
                    result.summary = f"Slice {slice_index + 1} analyzed successfully"
                    storage_gateway.write_json(output_file_path, parsed, ensure_ascii=False, indent=2)
        else:
            if hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    tool_result = tool_gateway.handle_tool_call(tool_call)
                    result.tool_results.append(tool_result)
                result.success = True
                result.summary = f"Slice {slice_index + 1} saved to {output_file_path}"
            else:
                result.success = True
                result.summary = choice.message.content
            _finalize_skills_slice_result(result, choice, output_file_path, storage_gateway)

    if choice is not None:
        _persist_slice_checkpoint_if_needed(
            checkpoint_id=checkpoint_id,
            slice_index=slice_index,
            mode=mode,
            output_file_path=output_file_path,
            choice=choice,
            result=result,
            ckpt_manager=ckpt_manager,
            storage_gateway=storage_gateway,
        )

    return result


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


def _sanitize_summarize_resumed(
    _request_data: SummarizeRequest,
    checkpoint_data: Any,
    runtime: TaskRuntimeDependencies,
) -> None:
    """清理恢复后的 summarize 进度。

    Args:
        _request_data: 归纳请求。
        checkpoint_data: checkpoint 预处理结果。
        runtime: 任务运行时依赖。

    Returns:
        None

    Raises:
        Exception: 进度修正失败时向上抛出。
    """
    ckpt = checkpoint_data.state.checkpoint
    _sanitize_resume_progress(ckpt, runtime.checkpoint_gateway, checkpoint_data.checkpoint_id)


_on_summarize_resumed = chain_on_resumed(
    _sanitize_summarize_resumed,
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
        checkpoint_task_type="summarize",
        load_resume_state=lambda _gateway, _checkpoint_id, checkpoint: SummarizeResumeState(checkpoint=checkpoint),
        build_initial_state=lambda: SummarizeResumeState(checkpoint={}),
        load_resumable_checkpoint_fn=load_resumable_checkpoint,
        build_prepared=_build_prepared_summarize_task,
        validate_before_checkpoint=_validate_summarize_before_checkpoint,
        validate_after_checkpoint=_validate_summarize_after_checkpoint,
        on_resumed=_on_summarize_resumed,
    )


def _sanitize_resume_progress(
    ckpt: dict[str, Any],
    checkpoint_gateway: Any,
    checkpoint_id: str,
) -> None:
    """修正恢复任务的进度数据。

    Args:
        ckpt: checkpoint 数据。
        checkpoint_gateway: checkpoint 网关。
        checkpoint_id: checkpoint 标识。

    Returns:
        None

    Raises:
        Exception: 进度更新失败时向上抛出。
    """
    if ckpt.get('task_type') != 'summarize':
        return

    progress = ckpt.get('progress', {})
    completed = list(progress.get('completed_items', []))
    if not completed:
        return

    valid_completed = []
    invalid_completed = []
    for index in completed:
        content = checkpoint_gateway.get_slice_result(checkpoint_id, index)
        if isinstance(content, str) and content.strip():
            valid_completed.append(index)
        else:
            invalid_completed.append(index)

    if not invalid_completed:
        return

    pending = list(progress.get('pending_items', []))
    pending_set = set(pending)
    for index in invalid_completed:
        pending_set.add(index)
    pending_clean = [index for index in sorted(pending_set) if index not in set(valid_completed)]

    progress['completed_items'] = valid_completed
    progress['pending_items'] = pending_clean
    checkpoint_gateway.update_progress(
        checkpoint_id,
        completed_items=valid_completed,
        pending_items=pending_clean,
    )


def _build_summary_dir(file_paths: list[str], role_name: str) -> str:
    """构造 summary 输出目录。

    Args:
        file_paths: 输入文件路径列表。
        role_name: 角色名。

    Returns:
        str: summary 输出目录路径。

    Raises:
        Exception: 目录路径构造失败时向上抛出。
    """
    summaries_root = get_workspace_summaries_dir()
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
) -> SummarizeExecutionAggregate:
    """并发执行切片任务。

    Args:
        tasks: 切片任务列表。
        request_data: 归纳请求。
        runtime: 任务运行时依赖。

    Returns:
        SummarizeExecutionAggregate: 归纳执行汇总结果。

    Raises:
        Exception: 线程池执行异常未被内部拦截时向上抛出。
    """
    execution = SummarizeExecutionAggregate()

    with runtime.executor_gateway.create(max_workers=request_data.concurrency) as executor:
        future_to_task = {
            executor.submit(
                _process_single_slice,
                task,
                runtime.checkpoint_gateway,
                runtime.llm_gateway,
                runtime.tool_gateway,
                runtime.storage_gateway,
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
                    execution.errors.append(f'切片 {result.index + 1} 处理失败')
            except Exception as e:
                task = future_to_task[future]
                execution.errors.append(f'切片 {task.slice_index + 1} 处理异常: {str(e)}')

    return execution


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
    runtime.llm_gateway.set_total_requests(len(current_slices))

    summary_dir = _build_summary_dir(request_data.file_paths, request_data.role_name)
    runtime.storage_gateway.makedirs(summary_dir, exist_ok=True)

    if not request_data.resume_checkpoint_id:
        runtime.checkpoint_gateway.update_progress(
            checkpoint_id,
            total_steps=len(current_slices),
            pending_items=list(range(len(current_slices)))
        )

    tasks = _build_slice_tasks(current_slices, summary_dir, request_data, config, checkpoint_id)
    execution = _execute_slice_tasks(tasks, request_data, runtime)

    return _finalize_summarize_result(
        request_data=request_data,
        current_slices=current_slices,
        summary_dir=summary_dir,
        execution=execution,
        checkpoint_id=checkpoint_id,
        runtime=runtime,
    )
