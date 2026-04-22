"""Checkpoint 查询模块。"""

from typing import Any

from .store import CheckpointStore


class CheckpointQueryService:
    """封装 checkpoint 列表与明细查询。"""

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store

    def list_checkpoints(
        self,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        checkpoints: list[dict[str, Any]] = []
        for checkpoint_id in self.store.list_checkpoint_ids():
            data = self.store.load_checkpoint(checkpoint_id)
            if not data:
                continue
            if task_type and data["task_type"] != task_type:
                continue
            if status and data["status"] != status:
                continue
            checkpoints.append(
                {
                    "checkpoint_id": data["checkpoint_id"],
                    "task_type": data["task_type"],
                    "status": data["status"],
                    "created_at": data["created_at"],
                    "updated_at": data["updated_at"],
                    "progress": data["progress"],
                    "input_params": {
                        key: value
                        for key, value in data.get("input_params", {}).items()
                        if key != "vndb_data"
                    },
                }
            )
        return sorted(checkpoints, key=lambda item: item["updated_at"], reverse=True)


__all__ = ["CheckpointQueryService"]
