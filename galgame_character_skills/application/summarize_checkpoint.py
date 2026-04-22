"""summarize checkpoint 协调模块，负责恢复进度修正与切片结果持久化。"""

import json
from typing import Any, Callable

from .app_container import TaskRuntimeDependencies
from .runtime_logging import log_message
from .task_prepare_context import chain_on_resumed
from ..domain import TASK_TYPE_SUMMARIZE


def build_checkpoint_slice_content(
    mode: str,
    output_file_path: str,
    choice: Any,
    result: Any,
    storage_gateway: Any,
) -> str:
    """构造切片 checkpoint 内容。

    Args:
        mode: 归纳模式。
        output_file_path: 切片输出路径。
        choice: LLM 返回选择项。
        result: 切片执行结果对象。
        storage_gateway: 存储网关。

    Returns:
        str: 用于写入 checkpoint 的切片内容。

    Raises:
        Exception: 内容提取失败时向上抛出。
    """
    if mode == "chara_card":
        return storage_gateway.read_text(output_file_path)

    try:
        if storage_gateway.exists(output_file_path):
            return storage_gateway.read_text(output_file_path)
    except Exception:
        pass

    if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
        for tool_call in choice.message.tool_calls:
            if hasattr(tool_call, "function") and tool_call.function.name == "write_file":
                args_dict = json.loads(tool_call.function.arguments)
                return args_dict.get("content", "")

    return result["summary"] or ""


def persist_slice_checkpoint_if_needed(
    checkpoint_id: str | None,
    slice_index: int,
    mode: str,
    output_file_path: str,
    choice: Any,
    result: Any,
    checkpoint_gateway: Any,
    storage_gateway: Any,
    logger: Callable[[str], None] | None = None,
) -> None:
    """按需持久化切片 checkpoint。

    Args:
        checkpoint_id: checkpoint 标识。
        slice_index: 切片索引。
        mode: 归纳模式。
        output_file_path: 切片输出路径。
        choice: LLM 返回选择项。
        result: 切片执行结果对象。
        checkpoint_gateway: checkpoint 网关。
        storage_gateway: 存储网关。
        logger: 日志函数。

    Returns:
        None

    Raises:
        Exception: checkpoint 保存异常未被内部拦截时向上抛出。
    """
    if not (result.success and checkpoint_id):
        return

    try:
        ckpt_content = build_checkpoint_slice_content(
            mode=mode,
            output_file_path=output_file_path,
            choice=choice,
            result=result,
            storage_gateway=storage_gateway,
        )
        checkpoint_gateway.save_slice_result(checkpoint_id, slice_index, ckpt_content, "completed")
        checkpoint_gateway.mark_slice_completed(checkpoint_id, slice_index)
    except Exception as exc:
        log_message(f"Failed to save slice {slice_index} result: {exc}", logger=logger)


def sanitize_resume_progress(
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
    if ckpt.get("task_type") != TASK_TYPE_SUMMARIZE:
        return

    progress = ckpt.get("progress", {})
    completed = list(progress.get("completed_items", []))
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

    pending = list(progress.get("pending_items", []))
    pending_set = set(pending)
    for index in invalid_completed:
        pending_set.add(index)
    pending_clean = [index for index in sorted(pending_set) if index not in set(valid_completed)]

    progress["completed_items"] = valid_completed
    progress["pending_items"] = pending_clean
    checkpoint_gateway.update_progress(
        checkpoint_id,
        completed_items=valid_completed,
        pending_items=pending_clean,
    )


def sanitize_summarize_resumed(
    _request_data: Any,
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
    sanitize_resume_progress(ckpt, runtime.checkpoint_gateway, checkpoint_data.checkpoint_id)


def build_summarize_resumed_handler(
    *handlers: Callable[[Any, Any, TaskRuntimeDependencies], None] | None,
) -> Callable[[Any, Any, TaskRuntimeDependencies], None]:
    """构造 summarize 恢复后的组合回调。

    Args:
        *handlers: 恢复后附加执行的回调函数。

    Returns:
        Callable[[Any, Any, TaskRuntimeDependencies], None]: 组合后的回调函数。

    Raises:
        Exception: 回调构造失败时向上抛出。
    """
    return chain_on_resumed(sanitize_summarize_resumed, *handlers)


__all__ = [
    "build_checkpoint_slice_content",
    "persist_slice_checkpoint_if_needed",
    "sanitize_resume_progress",
    "sanitize_summarize_resumed",
    "build_summarize_resumed_handler",
]
