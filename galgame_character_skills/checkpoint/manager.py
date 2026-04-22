"""Checkpoint 持久化管理模块，聚合各类 checkpoint 读写能力。"""

import os
import threading
from typing import Any

from .cleanup import CheckpointCleanupService
from .llm_state import CheckpointLLMStateService
from .progress import CheckpointProgressService
from .query import CheckpointQueryService
from .slice_results import CheckpointSliceResultService
from .store import CheckpointStore
from ..workspace import get_workspace_checkpoints_dir


class CheckpointManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(
        cls,
        checkpoint_dir: str | None = None,
        use_singleton: bool = True,
    ) -> "CheckpointManager":
        """创建 checkpoint 管理器实例。"""
        if not use_singleton:
            obj = super().__new__(cls)
            obj._initialized = False
            obj._init_dir = checkpoint_dir
            return obj

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                    cls._instance._init_dir = checkpoint_dir
        return cls._instance

    def __init__(
        self,
        checkpoint_dir: str | None = None,
        use_singleton: bool = True,
    ) -> None:
        """初始化 checkpoint 管理器。"""
        if self._initialized:
            return
        if checkpoint_dir is None:
            checkpoint_dir = self._init_dir
        if checkpoint_dir is None:
            checkpoint_dir = get_workspace_checkpoints_dir()

        self.checkpoint_dir = checkpoint_dir
        self.temp_dir = os.path.join(checkpoint_dir, "temp")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        self.store = CheckpointStore(self.checkpoint_dir, self.temp_dir)
        self.progress = CheckpointProgressService(self.store)
        self.llm_state = CheckpointLLMStateService(self.store)
        self.slice_results = CheckpointSliceResultService(self.store)
        self.query = CheckpointQueryService(self.store)
        self.cleanup = CheckpointCleanupService(self.store)
        self._initialized = True

    @classmethod
    def create_test_instance(cls, checkpoint_dir: str) -> "CheckpointManager":
        """创建测试专用管理器实例。"""
        return cls(checkpoint_dir=checkpoint_dir, use_singleton=False)

    def create_checkpoint(
        self,
        task_type: str,
        input_params: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """创建新的 checkpoint。"""
        return self.store.create_checkpoint(task_type=task_type, input_params=input_params, metadata=metadata)

    def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """加载 checkpoint 数据。"""
        return self.store.load_checkpoint(checkpoint_id)

    def update_progress(
        self,
        checkpoint_id: str,
        current_step: int | None = None,
        total_steps: int | None = None,
        current_phase: str | None = None,
        completed_items: list[Any] | None = None,
        failed_items: list[Any] | None = None,
        pending_items: list[Any] | None = None,
    ) -> None:
        """更新 checkpoint 进度。"""
        self.progress.update_progress(
            checkpoint_id=checkpoint_id,
            current_step=current_step,
            total_steps=total_steps,
            current_phase=current_phase,
            completed_items=completed_items,
            failed_items=failed_items,
            pending_items=pending_items,
        )

    def save_slice_result(
        self,
        checkpoint_id: str,
        slice_index: int,
        content: str,
        status: str = "completed",
    ) -> str | None:
        """保存切片结果文件。"""
        return self.slice_results.save_slice_result(
            checkpoint_id=checkpoint_id,
            slice_index=slice_index,
            content=content,
            status=status,
        )

    def mark_slice_completed(self, checkpoint_id: str, slice_index: int) -> None:
        """标记切片已完成。"""
        self.progress.mark_slice_completed(checkpoint_id, slice_index)

    def get_slice_result(self, checkpoint_id: str, slice_index: int) -> str | None:
        """读取切片结果内容。"""
        return self.slice_results.get_slice_result(checkpoint_id, slice_index)

    def save_llm_state(
        self,
        checkpoint_id: str,
        messages: list[Any],
        last_response: Any = None,
        iteration_count: int | None = None,
        tool_call_history: list[Any] | None = None,
        all_results: list[Any] | None = None,
        fields_data: dict[str, Any] | None = None,
        extra_data: dict[str, Any] | None = None,
    ) -> None:
        """保存 LLM 会话状态。"""
        self.llm_state.save_llm_state(
            checkpoint_id=checkpoint_id,
            messages=messages,
            last_response=last_response,
            iteration_count=iteration_count,
            tool_call_history=tool_call_history,
            all_results=all_results,
            fields_data=fields_data,
            extra_data=extra_data,
        )

    def load_llm_state(self, checkpoint_id: str) -> dict[str, Any] | None:
        """加载 LLM 会话状态。"""
        return self.llm_state.load_llm_state(checkpoint_id)

    def mark_completed(
        self,
        checkpoint_id: str,
        final_output_path: str | None = None,
    ) -> None:
        """标记任务完成。"""
        self.progress.mark_completed(checkpoint_id, final_output_path=final_output_path)

    def mark_failed(self, checkpoint_id: str, error_message: str) -> None:
        """标记任务失败。"""
        self.progress.mark_failed(checkpoint_id, error_message)

    def list_checkpoints(
        self,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出 checkpoint 概览。"""
        return self.query.list_checkpoints(task_type=task_type, status=status)

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除 checkpoint 及其临时文件。"""
        return self.cleanup.delete_checkpoint(checkpoint_id)

    def get_temp_dir(self, checkpoint_id: str) -> str:
        """获取并确保存在临时目录。"""
        return self.store.get_temp_dir(checkpoint_id)


__all__ = ["CheckpointManager"]
