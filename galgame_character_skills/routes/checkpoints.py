"""Checkpoint 路由注册模块。"""

from flask import request

from ..api.checkpoint_api import CheckpointApi


def register_checkpoint_routes(app, runtime, adapter) -> None:
    """注册 checkpoint 相关路由。"""
    checkpoint_api = CheckpointApi(runtime)

    @app.route("/api/checkpoints", methods=["GET"])
    def list_checkpoints():
        """处理 checkpoint 列表查询请求。

        Args:
            None

        Returns:
            Response: checkpoint 列表 JSON 响应。

        Raises:
            Exception: 查询参数读取或列表获取失败时向上抛出。
        """
        task_type = request.args.get("task_type")
        status = request.args.get("status")
        return adapter.run(checkpoint_api.list_checkpoints, task_type=task_type, status=status)

    @app.route("/api/checkpoints/<checkpoint_id>", methods=["GET"])
    def get_checkpoint(checkpoint_id):
        """处理 checkpoint 详情查询请求。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            Response: checkpoint 详情 JSON 响应。

        Raises:
            Exception: 详情读取失败时向上抛出。
        """
        return adapter.run(checkpoint_api.get_checkpoint, checkpoint_id)

    @app.route("/api/checkpoints/<checkpoint_id>", methods=["DELETE"])
    def delete_checkpoint(checkpoint_id):
        """处理 checkpoint 删除请求。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            Response: 删除结果 JSON 响应。

        Raises:
            Exception: 删除执行失败时向上抛出。
        """
        return adapter.run(checkpoint_api.delete_checkpoint, checkpoint_id)

    @app.route("/api/checkpoints/<checkpoint_id>/resume", methods=["POST"])
    def resume_checkpoint(checkpoint_id):
        """处理 checkpoint 恢复请求。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            Response: 恢复执行结果 JSON 响应。

        Raises:
            Exception: 请求解析或任务恢复失败时向上抛出。
        """
        return adapter.run_with_body(checkpoint_api.resume_checkpoint, checkpoint_id)


__all__ = ["register_checkpoint_routes"]
