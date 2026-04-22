"""Checkpoint 恢复模块，负责校验状态并返回可恢复任务的上下文。"""

from typing import Any

from ..domain import ok_result, fail_result


def load_resumable_checkpoint(ckpt_manager: Any, checkpoint_id: str) -> dict[str, Any]:
    """加载可恢复的 checkpoint。

    Args:
        ckpt_manager: checkpoint 管理器。
        checkpoint_id: checkpoint 标识。

    Returns:
        dict[str, Any]: 可恢复 checkpoint 结果。

    Raises:
        Exception: checkpoint 读取失败时向上抛出。
    """
    ckpt = ckpt_manager.load_checkpoint(checkpoint_id)
    if not ckpt:
        return fail_result(f'未找到Checkpoint: {checkpoint_id}')
    if ckpt['status'] == 'running':
        return fail_result('该任务正在运行，请稍后刷新状态')
    if ckpt['status'] == 'completed':
        return fail_result('该任务已完成，无需恢复')
    return ok_result(checkpoint=ckpt)
