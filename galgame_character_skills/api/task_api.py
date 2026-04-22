"""任务 API facade，集中封装任务相关接口入口。"""

from typing import Any

from ..application.app_container import TaskRuntimeDependencies
from ..application.summarize_service import run_summarize_task
from ..application.skills_service import run_generate_skills_task
from ..application.character_card_service import run_generate_character_card_task
from .validators import require_non_empty_field


class TaskApi:
    """任务接口 facade。"""

    def __init__(self, runtime: TaskRuntimeDependencies) -> None:
        self.runtime = runtime

    def summarize(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行 summarize 任务接口。"""
        return run_summarize_task(data=data, runtime=self.runtime)

    def generate_skills_folder(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行技能包生成任务接口。"""
        return run_generate_skills_task(data=data, runtime=self.runtime)

    def generate_character_card(self, data: dict[str, Any]) -> dict[str, Any]:
        """执行角色卡生成任务接口。"""
        return run_generate_character_card_task(data=data, runtime=self.runtime)

    @require_non_empty_field("role_name", "请输入角色名称", data_arg_index=1)
    def dispatch_skills_mode(self, data: dict[str, Any]) -> dict[str, Any]:
        """按模式分发技能相关任务。"""
        mode = data.get("mode", "skills")

        if mode == "chara_card":
            return self.generate_character_card(data)
        return self.generate_skills_folder(data)


__all__ = ["TaskApi"]
