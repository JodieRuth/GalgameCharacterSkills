"""Checkpoint 网关模块，抽象并默认实现 checkpoint 相关底层操作。"""

from typing import Any


class CheckpointGateway:
    def create_checkpoint(
        self,
        task_type: str,
        input_params: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """创建 checkpoint。

        Args:
            task_type: 任务类型。
            input_params: 输入参数。
            metadata: 附加元数据。

        Returns:
            str: checkpoint 标识。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """加载 checkpoint。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            dict[str, Any] | None: checkpoint 数据。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def update_progress(self, checkpoint_id: str, **kwargs: Any) -> Any:
        """更新 checkpoint 进度。

        Args:
            checkpoint_id: checkpoint 标识。
            **kwargs: 进度字段。

        Returns:
            Any: 更新结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def save_slice_result(
        self,
        checkpoint_id: str,
        slice_index: int,
        content: str,
        status: str = "completed",
    ) -> Any:
        """保存切片结果。

        Args:
            checkpoint_id: checkpoint 标识。
            slice_index: 切片索引。
            content: 切片内容。
            status: 切片状态。

        Returns:
            Any: 保存结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def get_slice_result(self, checkpoint_id: str, slice_index: int) -> Any:
        """获取切片结果。

        Args:
            checkpoint_id: checkpoint 标识。
            slice_index: 切片索引。

        Returns:
            Any: 切片结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def mark_slice_completed(self, checkpoint_id: str, slice_index: int) -> Any:
        """标记切片完成。

        Args:
            checkpoint_id: checkpoint 标识。
            slice_index: 切片索引。

        Returns:
            Any: 标记结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def save_llm_state(self, checkpoint_id: str, messages: list[Any], **kwargs: Any) -> Any:
        """保存 LLM 状态。

        Args:
            checkpoint_id: checkpoint 标识。
            messages: 消息列表。
            **kwargs: 额外状态字段。

        Returns:
            Any: 保存结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def load_llm_state(self, checkpoint_id: str) -> dict[str, Any]:
        """加载 LLM 状态。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            dict[str, Any]: LLM 状态数据。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def mark_completed(self, checkpoint_id: str, final_output_path: str | None = None) -> Any:
        """标记任务完成。

        Args:
            checkpoint_id: checkpoint 标识。
            final_output_path: 最终输出路径。

        Returns:
            Any: 标记结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def mark_failed(self, checkpoint_id: str, error_message: str) -> Any:
        """标记任务失败。

        Args:
            checkpoint_id: checkpoint 标识。
            error_message: 错误消息。

        Returns:
            Any: 标记结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def list_checkpoints(
        self,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出 checkpoint。

        Args:
            task_type: 任务类型过滤条件。
            status: 状态过滤条件。

        Returns:
            list[dict[str, Any]]: checkpoint 列表。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除 checkpoint。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            bool: 是否删除成功。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def get_temp_dir(self, checkpoint_id: str) -> str:
        """获取 checkpoint 临时目录。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            str: 临时目录路径。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError


class DefaultCheckpointGateway(CheckpointGateway):
    def __init__(self, manager: Any) -> None:
        """初始化默认 checkpoint 网关。

        Args:
            manager: checkpoint 管理器。

        Returns:
            None

        Raises:
            Exception: 初始化失败时向上抛出。
        """
        self.manager = manager

    def create_checkpoint(
        self,
        task_type: str,
        input_params: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """创建 checkpoint。"""
        return self.manager.create_checkpoint(task_type=task_type, input_params=input_params, metadata=metadata)

    def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """加载 checkpoint。"""
        return self.manager.load_checkpoint(checkpoint_id)

    def update_progress(self, checkpoint_id: str, **kwargs: Any) -> Any:
        """更新 checkpoint 进度。"""
        return self.manager.update_progress(checkpoint_id, **kwargs)

    def save_slice_result(
        self,
        checkpoint_id: str,
        slice_index: int,
        content: str,
        status: str = "completed",
    ) -> Any:
        """保存切片结果。"""
        return self.manager.save_slice_result(checkpoint_id, slice_index, content, status)

    def get_slice_result(self, checkpoint_id: str, slice_index: int) -> Any:
        """获取切片结果。"""
        return self.manager.get_slice_result(checkpoint_id, slice_index)

    def mark_slice_completed(self, checkpoint_id: str, slice_index: int) -> Any:
        """标记切片完成。"""
        return self.manager.mark_slice_completed(checkpoint_id, slice_index)

    def save_llm_state(self, checkpoint_id: str, messages: list[Any], **kwargs: Any) -> Any:
        """保存 LLM 状态。"""
        return self.manager.save_llm_state(checkpoint_id, messages, **kwargs)

    def load_llm_state(self, checkpoint_id: str) -> dict[str, Any]:
        """加载 LLM 状态。"""
        return self.manager.load_llm_state(checkpoint_id)

    def mark_completed(self, checkpoint_id: str, final_output_path: str | None = None) -> Any:
        """标记任务完成。"""
        return self.manager.mark_completed(checkpoint_id, final_output_path=final_output_path)

    def mark_failed(self, checkpoint_id: str, error_message: str) -> Any:
        """标记任务失败。"""
        return self.manager.mark_failed(checkpoint_id, error_message)

    def list_checkpoints(
        self,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出 checkpoint。"""
        return self.manager.list_checkpoints(task_type=task_type, status=status)

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除 checkpoint。"""
        return self.manager.delete_checkpoint(checkpoint_id)

    def get_temp_dir(self, checkpoint_id: str) -> str:
        """获取 checkpoint 临时目录。"""
        return self.manager.get_temp_dir(checkpoint_id)


__all__ = ["CheckpointGateway", "DefaultCheckpointGateway"]
