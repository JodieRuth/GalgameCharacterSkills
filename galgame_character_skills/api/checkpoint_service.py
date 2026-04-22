"""Checkpoint 接口服务模块，提供列表、详情、删除与恢复任务的编排入口。"""

from typing import Any, Callable

from ..checkpoint import load_resumable_checkpoint
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


def resume_checkpoint_result(
    ckpt_manager: Any,
    checkpoint_id: str,
    extra_params: dict[str, Any] | None,
    summarize_handler: Callable[[dict[str, Any]], dict[str, Any]],
    generate_skills_handler: Callable[[dict[str, Any]], dict[str, Any]],
    generate_chara_card_handler: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """恢复指定 checkpoint 对应的任务。

    Args:
        ckpt_manager: checkpoint 管理器。
        checkpoint_id: checkpoint 标识。
        extra_params: 额外覆盖参数。
        summarize_handler: summarize 任务处理函数。
        generate_skills_handler: 技能包任务处理函数。
        generate_chara_card_handler: 角色卡任务处理函数。

    Returns:
        dict[str, Any]: 恢复执行结果。

    Raises:
        Exception: checkpoint 恢复或任务执行失败时向上抛出。
    """
    ckpt_result = load_resumable_checkpoint(ckpt_manager, checkpoint_id)
    if not ckpt_result.get('success'):
        return ckpt_result
    ckpt = ckpt_result['checkpoint']

    task_type = ckpt['task_type']
    input_params = dict(ckpt.get('input_params', {}))
    input_params['resume_checkpoint_id'] = checkpoint_id
    input_params.update(extra_params or {})

    if task_type == 'summarize':
        return summarize_handler(input_params)
    if task_type == 'generate_skills':
        return generate_skills_handler(input_params)
    if task_type == 'generate_chara_card':
        return generate_chara_card_handler(input_params)
    return fail_result(f'未知的任务类型: {task_type}')


def resume_checkpoint_with_payload_result(
    data: dict[str, Any],
    checkpoint_id: str,
    ckpt_manager: Any,
    summarize_handler: Callable[[dict[str, Any]], dict[str, Any]],
    generate_skills_handler: Callable[[dict[str, Any]], dict[str, Any]],
    generate_chara_card_handler: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """使用请求载荷恢复 checkpoint 任务。

    Args:
        data: 请求数据。
        checkpoint_id: checkpoint 标识。
        ckpt_manager: checkpoint 管理器。
        summarize_handler: summarize 任务处理函数。
        generate_skills_handler: 技能包任务处理函数。
        generate_chara_card_handler: 角色卡任务处理函数。

    Returns:
        dict[str, Any]: 恢复执行结果。

    Raises:
        Exception: checkpoint 恢复或任务执行失败时向上抛出。
    """
    return resume_checkpoint_result(
        ckpt_manager=ckpt_manager,
        checkpoint_id=checkpoint_id,
        extra_params=data,
        summarize_handler=summarize_handler,
        generate_skills_handler=generate_skills_handler,
        generate_chara_card_handler=generate_chara_card_handler
    )
