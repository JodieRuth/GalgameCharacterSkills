"""Checkpoint 清理模块。"""

import os

from .store import CheckpointStore


class CheckpointCleanupService:
    """封装 checkpoint 删除与临时目录清理。"""

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        path = self.store.get_checkpoint_path(checkpoint_id)
        temp_path = os.path.join(self.store.temp_dir, checkpoint_id)
        has_record = (
            checkpoint_id in self.store._active_checkpoints
            or os.path.exists(path)
            or os.path.exists(temp_path)
        )
        if not has_record:
            return False

        self.store.cleanup_temp_dir(checkpoint_id)
        if not self.store.remove_checkpoint_file(checkpoint_id):
            return False
        self.store.remove_from_cache(checkpoint_id)
        return True


__all__ = ["CheckpointCleanupService"]
