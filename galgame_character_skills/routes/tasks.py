"""任务相关路由注册模块。"""

from ..api.task_api import TaskApi


def register_task_routes(app, runtime, adapter) -> None:
    """注册任务相关路由。"""
    task_api = TaskApi(runtime)

    @app.route("/api/summarize", methods=["POST"])
    def summarize():
        """处理 summarize 任务请求。

        Args:
            None

        Returns:
            Response: summarize 结果 JSON 响应。

        Raises:
            Exception: 请求解析或 summarize 执行失败时向上抛出。
        """
        return adapter.run_with_body(task_api.summarize)

    @app.route("/api/skills", methods=["POST"])
    def generate_skills():
        """处理技能包或角色卡任务请求。

        Args:
            None

        Returns:
            Response: 任务执行结果 JSON 响应。

        Raises:
            Exception: 请求解析或任务分发失败时向上抛出。
        """
        return adapter.run_with_body(task_api.dispatch_skills_mode)


__all__ = ["register_task_routes"]
