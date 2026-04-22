"""Checkpoint 接口服务模块，提供列表、详情与删除结果构造。"""

from typing import Any

from ..domain import ok_result, fail_result


def list_checkpoints_result(
    ckpt_manager: Any,
    task_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """获取 checkpoint 列表。

    Args:
        ckpt_manager: checkpoint 管理器。
        task_type: 任务类型过滤条件。
        status: 状态过滤条件。

    Returns:
        dict[str, Any]: checkpoint 列表结果。

    Raises:
        Exception: checkpoint 列表读取失败时向上抛出。
    """
    checkpoints = ckpt_manager.list_checkpoints(task_type=task_type, status=status)
    return ok_result(checkpoints=checkpoints)


def get_checkpoint_result(ckpt_manager: Any, checkpoint_id: str) -> dict[str, Any]:
    """获取 checkpoint 详情。

    Args:
        ckpt_manager: checkpoint 管理器。
        checkpoint_id: checkpoint 标识。

    Returns:
        dict[str, Any]: checkpoint 详情结果。

    Raises:
        Exception: checkpoint 读取失败时向上抛出。
    """
    ckpt = ckpt_manager.load_checkpoint(checkpoint_id)
    if not ckpt:
        return fail_result(f'未找到Checkpoint: {checkpoint_id}')
    llm_state = ckpt_manager.load_llm_state(checkpoint_id)
    return ok_result(checkpoint=ckpt, llm_state=llm_state)


def delete_checkpoint_result(ckpt_manager: Any, checkpoint_id: str) -> dict[str, Any]:
    """删除 checkpoint。

    Args:
        ckpt_manager: checkpoint 管理器。
        checkpoint_id: checkpoint 标识。

    Returns:
        dict[str, Any]: 删除结果。

    Raises:
        Exception: checkpoint 删除失败时向上抛出。
    """
    success = ckpt_manager.delete_checkpoint(checkpoint_id)
    if success:
        return ok_result(message='Checkpoint已删除')
    return fail_result(f'未找到Checkpoint: {checkpoint_id}')

