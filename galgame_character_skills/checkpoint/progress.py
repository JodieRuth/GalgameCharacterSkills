"""Checkpoint 进度与状态更新模块。"""

from typing import Any

from .store import CheckpointStore


class CheckpointProgressService:
    """封装 checkpoint 的进度与状态更新。"""

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store

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
        data = self.store.get_active_checkpoint(checkpoint_id)
        if not data:
            return
        progress = data["progress"]
        if current_step is not None:
            progress["current_step"] = current_step
        if total_steps is not None:
            progress["total_steps"] = total_steps
        if current_phase is not None:
            progress["current_phase"] = current_phase
        if completed_items is not None:
            progress["completed_items"] = completed_items
        if failed_items is not None:
            progress["failed_items"] = failed_items
        if pending_items is not None:
            progress["pending_items"] = pending_items
        self.store.save_checkpoint(checkpoint_id)

    def mark_slice_completed(self, checkpoint_id: str, slice_index: int) -> None:
        with self.store._file_lock:
            data = self.store.get_active_checkpoint(checkpoint_id)
            if not data:
                return
            progress = data.get("progress", {})
            completed = progress.setdefault("completed_items", [])
            pending = progress.setdefault("pending_items", [])
            if slice_index not in completed:
                completed.append(slice_index)
            progress["pending_items"] = [item for item in pending if item != slice_index]
            self.store.save_checkpoint(checkpoint_id)

    def mark_completed(self, checkpoint_id: str, final_output_path: str | None = None) -> None:
        data = self.store.get_active_checkpoint(checkpoint_id)
        if not data:
            return
        data["status"] = "completed"
        if final_output_path:
            data["intermediate_results"]["final_output_path"] = final_output_path
        self.store.save_checkpoint(checkpoint_id)

    def mark_failed(self, checkpoint_id: str, error_message: str) -> None:
        data = self.store.get_active_checkpoint(checkpoint_id)
        if not data:
            return
        data["status"] = "failed"
        data["progress"]["error_message"] = error_message
        self.store.save_checkpoint(checkpoint_id)


__all__ = ["CheckpointProgressService"]
