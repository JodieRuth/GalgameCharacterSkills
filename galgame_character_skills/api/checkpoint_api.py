"""Checkpoint API facade，集中封装 checkpoint 相关接口入口。"""

from typing import Any

from ..application.resume_dispatcher import ResumeTaskDispatcher, ResumeTaskHandler
from ..application.app_container import TaskRuntimeDependencies
from ..domain import (
    ok_result,
    fail_result,
    TASK_TYPE_SUMMARIZE,
    TASK_TYPE_GENERATE_SKILLS,
    TASK_TYPE_GENERATE_CHARA_CARD,
)
from .task_api import TaskApi


def build_resume_task_handlers(task_api: TaskApi) -> dict[str, ResumeTaskHandler]:
    """构造 checkpoint 恢复任务处理器映射。"""
    return {
        TASK_TYPE_SUMMARIZE: task_api.summarize,
        TASK_TYPE_GENERATE_SKILLS: task_api.generate_skills_folder,
        TASK_TYPE_GENERATE_CHARA_CARD: task_api.generate_character_card,
    }


class CheckpointApi:
    """Checkpoint 接口 facade。

    负责封装 checkpoint 列表、详情、删除与恢复等接口入口，
    对路由层隐藏具体的恢复分发与任务恢复细节。
    """

    def __init__(self, runtime: TaskRuntimeDependencies) -> None:
        """初始化 checkpoint 接口 facade。

        Args:
            runtime: 任务运行时依赖。

        Returns:
            None

        Raises:
            Exception: facade 初始化失败时向上抛出。
        """
        self.runtime = runtime
        task_api = TaskApi(runtime)
        self._resume_dispatcher = ResumeTaskDispatcher(build_resume_task_handlers(task_api))

    def list_checkpoints(
        self,
        task_type: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """获取 checkpoint 列表。

        Args:
            task_type: 任务类型过滤条件。
            status: 状态过滤条件。

        Returns:
            dict[str, Any]: checkpoint 列表结果。

        Raises:
            Exception: checkpoint 列表读取失败时向上抛出。
        """
        checkpoints = self.runtime.checkpoint_gateway.list_checkpoints(task_type=task_type, status=status)
        return ok_result(checkpoints=checkpoints)

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        """获取 checkpoint 详情。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            dict[str, Any]: checkpoint 详情结果。

        Raises:
            Exception: checkpoint 读取失败时向上抛出。
        """
        ckpt = self.runtime.checkpoint_gateway.load_checkpoint(checkpoint_id)
        if not ckpt:
            return fail_result(f"未找到Checkpoint: {checkpoint_id}")

        llm_state = self.runtime.checkpoint_gateway.load_llm_state(checkpoint_id)
        return ok_result(checkpoint=ckpt, llm_state=llm_state)

    def delete_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        """删除 checkpoint。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            dict[str, Any]: 删除结果。

        Raises:
            Exception: checkpoint 删除失败时向上抛出。
        """
        success = self.runtime.checkpoint_gateway.delete_checkpoint(checkpoint_id)
        if success:
            return ok_result(message="Checkpoint已删除")
        return fail_result(f"未找到Checkpoint: {checkpoint_id}")

    def resume_checkpoint(
        self,
        checkpoint_id: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """使用请求载荷恢复 checkpoint 任务。

        Args:
            checkpoint_id: checkpoint 标识。
            data: 恢复时覆盖的请求参数。

        Returns:
            dict[str, Any]: 恢复执行结果。

        Raises:
            Exception: checkpoint 恢复或任务执行失败时向上抛出。
        """
        return self._resume_dispatcher.resume(
            checkpoint_gateway=self.runtime.checkpoint_gateway,
            checkpoint_id=checkpoint_id,
            extra_params=data,
        )


__all__ = ["CheckpointApi", "build_resume_task_handlers"]
