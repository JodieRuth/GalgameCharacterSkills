"""任务恢复预处理模块，统一封装带 checkpoint 的请求准备过程。"""

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from ...checkpoint import load_resumable_checkpoint
from ...gateways.checkpoint_gateway import CheckpointGateway

StateT = TypeVar("StateT")
RequestT = TypeVar("RequestT")


@dataclass(frozen=True)
class PreparedCheckpointData(Generic[StateT]):
    checkpoint_id: str
    state: StateT
    resumed: bool
    checkpoint: dict[str, Any] | None


def prepare_request_with_checkpoint(
    request_data: RequestT,
    checkpoint_gateway: CheckpointGateway,
    task_type: str,
    load_resume_state: Callable[[CheckpointGateway, str, dict[str, Any]], StateT],
    build_initial_state: Callable[[], StateT],
    load_resumable_checkpoint_fn: Callable[[CheckpointGateway, str], dict[str, Any]] = load_resumable_checkpoint,
) -> tuple[PreparedCheckpointData[StateT] | None, dict[str, Any] | None]:
    """准备带 checkpoint 的任务请求上下文。

    Args:
        request_data: 已完成清洗的请求对象。
        checkpoint_gateway: checkpoint 网关。
        task_type: 任务类型标识。
        load_resume_state: 恢复状态加载函数。
        build_initial_state: 新任务初始状态构造函数。
        load_resumable_checkpoint_fn: checkpoint 恢复加载函数。

    Returns:
        tuple[PreparedCheckpointData[StateT] | None, dict[str, Any] | None]:
            prepared 数据和错误结果。

    Raises:
        Exception: checkpoint 读写失败时向上抛出。
    """
    if request_data.resume_checkpoint_id:
        ckpt_result = load_resumable_checkpoint_fn(checkpoint_gateway, request_data.resume_checkpoint_id)
        if not ckpt_result.get("success"):
            return None, ckpt_result

        ckpt = ckpt_result["checkpoint"]
        request_data.apply_checkpoint(ckpt["input_params"])
        checkpoint_id = request_data.resume_checkpoint_id
        state = load_resume_state(checkpoint_gateway, checkpoint_id, ckpt)
        return PreparedCheckpointData(
            checkpoint_id=checkpoint_id,
            state=state,
            resumed=True,
            checkpoint=ckpt,
        ), None

    checkpoint_id = checkpoint_gateway.create_checkpoint(
        task_type=task_type,
        input_params=request_data.to_checkpoint_input(),
    )
    return PreparedCheckpointData(
        checkpoint_id=checkpoint_id,
        state=build_initial_state(),
        resumed=False,
        checkpoint=None,
    ), None


__all__ = ["PreparedCheckpointData", "prepare_request_with_checkpoint"]
