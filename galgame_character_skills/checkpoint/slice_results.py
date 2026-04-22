"""Checkpoint 切片结果持久化模块。"""

import os

from .store import CheckpointStore


class CheckpointSliceResultService:
    """封装 summarize 切片结果的读写。"""

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store

    def save_slice_result(
        self,
        checkpoint_id: str,
        slice_index: int,
        content: str,
        status: str = "completed",
    ) -> str | None:
        data = self.store.get_active_checkpoint(checkpoint_id)
        if not data:
            return None
        slice_file = os.path.join(self.store.get_temp_dir(checkpoint_id), f"slice_{slice_index}.dat")
        try:
            with open(slice_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as exc:
            print(f"Failed to save slice {slice_index}: {exc}")
            return None

        data["intermediate_results"]["slice_outputs"][str(slice_index)] = {
            "temp_file": slice_file,
            "status": status,
        }
        self.store.save_checkpoint(checkpoint_id)
        return slice_file

    def get_slice_result(self, checkpoint_id: str, slice_index: int) -> str | None:
        data = self.store.get_active_checkpoint(checkpoint_id)
        if not data:
            return None
        slice_info = data["intermediate_results"]["slice_outputs"].get(str(slice_index))
        if not slice_info:
            return None
        temp_file = slice_info.get("temp_file")
        if not temp_file or not os.path.exists(temp_file):
            return None
        try:
            with open(temp_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None


__all__ = ["CheckpointSliceResultService"]
