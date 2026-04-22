"""Checkpoint 底层存储模块，负责文件读写、缓存与目录管理。"""

import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any


class CheckpointStore:
    """Checkpoint 底层存储对象。"""

    def __init__(self, checkpoint_dir: str, temp_dir: str) -> None:
        self.checkpoint_dir = checkpoint_dir
        self.temp_dir = temp_dir
        self._active_checkpoints: dict[str, dict[str, Any]] = {}
        self._file_lock = threading.RLock()

    def create_checkpoint(
        self,
        task_type: str,
        input_params: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        checkpoint_id = f"{task_type}_{uuid.uuid4().hex[:8]}"
        os.makedirs(self.get_temp_dir(checkpoint_id), exist_ok=True)

        now = datetime.now().isoformat()
        self._active_checkpoints[checkpoint_id] = {
            "checkpoint_id": checkpoint_id,
            "task_type": task_type,
            "status": "running",
            "created_at": now,
            "updated_at": now,
            "input_params": input_params,
            "progress": {
                "current_step": 0,
                "total_steps": 0,
                "current_phase": "initialized",
                "completed_items": [],
                "failed_items": [],
                "pending_items": [],
            },
            "intermediate_results": {
                "slice_outputs": {},
                "temp_files": {},
            },
            "llm_conversation_state": {
                "messages": [],
                "tool_call_history": [],
                "last_response": None,
                "iteration_count": 0,
                "all_results": [],
                "fields_data": {},
            },
            "metadata": metadata or {},
        }
        self.save_checkpoint(checkpoint_id)
        return checkpoint_id

    def get_checkpoint_path(self, checkpoint_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")

    def save_checkpoint(self, checkpoint_id: str) -> None:
        with self._file_lock:
            data = self._active_checkpoints.get(checkpoint_id)
            if not data:
                return
            data["updated_at"] = datetime.now().isoformat()
            path = self.get_checkpoint_path(checkpoint_id)
            temp_path = path + ".tmp"
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                shutil.move(temp_path, path)
            except Exception as exc:
                print(f"Failed to save {checkpoint_id}: {exc}")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

    def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        if checkpoint_id in self._active_checkpoints:
            return self._active_checkpoints[checkpoint_id]

        path = self.get_checkpoint_path(checkpoint_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            print(f"Failed to load {checkpoint_id}: {exc}")
            return None

        self._active_checkpoints[checkpoint_id] = data
        return data

    def get_active_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        return self.load_checkpoint(checkpoint_id)

    def list_checkpoint_ids(self) -> list[str]:
        if not os.path.exists(self.checkpoint_dir):
            return []
        return [filename[:-5] for filename in os.listdir(self.checkpoint_dir) if filename.endswith(".json")]

    def get_temp_dir(self, checkpoint_id: str) -> str:
        ckpt_dir = os.path.join(self.temp_dir, checkpoint_id)
        os.makedirs(ckpt_dir, exist_ok=True)
        return ckpt_dir

    def cleanup_temp_dir(self, checkpoint_id: str) -> None:
        ckpt_dir = os.path.join(self.temp_dir, checkpoint_id)
        if os.path.exists(ckpt_dir):
            try:
                shutil.rmtree(ckpt_dir, ignore_errors=True)
            except Exception:
                pass

    def remove_checkpoint_file(self, checkpoint_id: str) -> bool:
        path = self.get_checkpoint_path(checkpoint_id)
        if not os.path.exists(path):
            return True
        try:
            os.remove(path)
            return True
        except Exception:
            return False

    def remove_from_cache(self, checkpoint_id: str) -> None:
        self._active_checkpoints.pop(checkpoint_id, None)


__all__ = ["CheckpointStore"]
