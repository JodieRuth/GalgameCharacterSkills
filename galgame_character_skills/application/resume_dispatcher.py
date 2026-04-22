"""任务恢复分发模块，负责按 checkpoint 任务类型恢复对应任务。"""

from typing import Any, Callable

from ..checkpoint import load_resumable_checkpoint
from ..domain import fail_result


class ResumeTaskDispatcher:
    """按 checkpoint 任务类型分发恢复请求。

    负责将恢复后的输入参数回填为任务请求，并根据 checkpoint
    中记录的 task_type 调用对应任务处理函数。
    """

    def __init__(
        self,
        summarize_handler: Callable[[dict[str, Any]], dict[str, Any]],
        generate_skills_handler: Callable[[dict[str, Any]], dict[str, Any]],
        generate_character_card_handler: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """初始化恢复任务分发器。

        Args:
            summarize_handler: summarize 任务处理函数。
            generate_skills_handler: 技能包任务处理函数。
            generate_character_card_handler: 角色卡任务处理函数。

        Returns:
            None

        Raises:
            Exception: 分发器初始化失败时向上抛出。
        """
        self._summarize_handler = summarize_handler
        self._generate_skills_handler = generate_skills_handler
        self._generate_character_card_handler = generate_character_card_handler

    def resume(
        self,
        checkpoint_gateway: Any,
        checkpoint_id: str,
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """恢复指定 checkpoint 对应的任务。

        Args:
            checkpoint_gateway: checkpoint 网关。
            checkpoint_id: checkpoint 标识。
            extra_params: 恢复时附加或覆盖的请求参数。

        Returns:
            dict[str, Any]: 恢复执行结果。

        Raises:
            Exception: checkpoint 恢复或任务执行失败时向上抛出。
        """
        ckpt_result = load_resumable_checkpoint(checkpoint_gateway, checkpoint_id)
        if not ckpt_result.get("success"):
            return ckpt_result

        ckpt = ckpt_result["checkpoint"]
        task_type = ckpt["task_type"]
        input_params = dict(ckpt.get("input_params", {}))
        input_params["resume_checkpoint_id"] = checkpoint_id
        input_params.update(extra_params or {})

        if task_type == "summarize":
            return self._summarize_handler(input_params)
        if task_type == "generate_skills":
            return self._generate_skills_handler(input_params)
        if task_type == "generate_chara_card":
            return self._generate_character_card_handler(input_params)
        return fail_result(f"未知的任务类型: {task_type}")


__all__ = ["ResumeTaskDispatcher"]
