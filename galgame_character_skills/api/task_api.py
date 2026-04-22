"""任务 API facade，集中封装任务相关接口入口。"""

from typing import Any

from ..application.app_container import TaskRuntimeDependencies
from ..application.summarize.service import run_summarize_task
from ..application.skills.service import run_generate_skills_task
from ..application.character_card.service import run_generate_character_card_task
from .validators import require_non_empty_field


class TaskApi:
    """任务接口 facade。

    负责将路由层的任务请求转发到对应的 application 用例，
    对外暴露稳定的 summarize / skills / character-card 入口。
    """

    def __init__(self, runtime: TaskRuntimeDependencies) -> None:
        """初始化任务接口 facade。

        Args:
            runtime: 任务运行时依赖。

        Returns:
            None

        Raises:
            Exception: facade 初始化失败时向上抛出。
        """
        self.runtime = runtime

    def summarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行 summarize 任务接口。

        Args:
            data: 请求数据。

        Returns:
            dict[str, Any]: summarize 任务结果。

        Raises:
            Exception: summarize 执行失败时向上抛出。
        """
        return run_summarize_task(data=data, runtime=self.runtime)

    def generate_skills_folder(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行技能包生成任务接口。

        Args:
            data: 请求数据。

        Returns:
            dict[str, Any]: 技能包生成结果。

        Raises:
            Exception: 技能包生成失败时向上抛出。
        """
        return run_generate_skills_task(data=data, runtime=self.runtime)

    def generate_character_card(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行角色卡生成任务接口。

        Args:
            data: 请求数据。

        Returns:
            dict[str, Any]: 角色卡生成结果。

        Raises:
            Exception: 角色卡生成失败时向上抛出。
        """
        return run_generate_character_card_task(data=data, runtime=self.runtime)

    @require_non_empty_field("role_name", "请输入角色名称", data_arg_index=1)
    def dispatch_skills_mode(self, data: dict[str, Any]) -> dict[str, Any]:
        """按模式分发技能相关任务。

        Args:
            data: 请求数据。

        Returns:
            dict[str, Any]: 分发后的任务结果。

        Raises:
            Exception: 分发或下游任务执行失败时向上抛出。
        """
        mode = data.get("mode", "skills")

        if mode == "chara_card":
            return self.generate_character_card(data)
        return self.generate_skills_folder(data)


__all__ = ["TaskApi"]
