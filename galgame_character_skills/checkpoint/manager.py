"""Checkpoint 持久化管理模块，负责状态存储、进度更新与任务目录维护。"""

import json
import os
import uuid
import shutil
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..workspace import get_workspace_checkpoints_dir


class CheckpointManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(
        cls,
        checkpoint_dir: str | None = None,
        use_singleton: bool = True,
    ) -> "CheckpointManager":
        """创建 checkpoint 管理器实例。

        Args:
            checkpoint_dir: checkpoint 存储目录。
            use_singleton: 是否启用单例。

        Returns:
            CheckpointManager: 管理器实例。

        Raises:
            Exception: 实例创建失败时向上抛出。
        """
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
        """初始化 checkpoint 管理器。

        Args:
            checkpoint_dir: checkpoint 存储目录。
            use_singleton: 是否启用单例。

        Returns:
            None

        Raises:
            Exception: 初始化失败时向上抛出。
        """
        if self._initialized:
            return
        if checkpoint_dir is None:
            checkpoint_dir = self._init_dir
        if checkpoint_dir is None:
            checkpoint_dir = get_workspace_checkpoints_dir()

        self.checkpoint_dir = checkpoint_dir
        self.temp_dir = os.path.join(checkpoint_dir, 'temp')
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        self._active_checkpoints: Dict[str, dict] = {}
        self._file_lock = threading.RLock()
        self._initialized = True

    @classmethod
    def create_test_instance(cls, checkpoint_dir: str) -> "CheckpointManager":
        """创建测试专用管理器实例。

        Args:
            checkpoint_dir: checkpoint 存储目录。

        Returns:
            CheckpointManager: 非单例管理器实例。

        Raises:
            Exception: 实例创建失败时向上抛出。
        """
        return cls(checkpoint_dir=checkpoint_dir, use_singleton=False)

    def create_checkpoint(
        self,
        task_type: str,
        input_params: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """创建新的 checkpoint。

        Args:
            task_type: 任务类型。
            input_params: 输入参数。
            metadata: 附加元数据。

        Returns:
            str: checkpoint 标识。

        Raises:
            Exception: checkpoint 创建失败时向上抛出。
        """
        checkpoint_id = f"{task_type}_{uuid.uuid4().hex[:8]}"
        ckpt_dir = os.path.join(self.temp_dir, checkpoint_id)
        os.makedirs(ckpt_dir, exist_ok=True)

        now = datetime.now().isoformat()
        data = {
            'checkpoint_id': checkpoint_id,
            'task_type': task_type,
            'status': 'running',
            'created_at': now,
            'updated_at': now,
            'input_params': input_params,
            'progress': {
                'current_step': 0,
                'total_steps': 0,
                'current_phase': 'initialized',
                'completed_items': [],
                'failed_items': [],
                'pending_items': []
            },
            'intermediate_results': {
                'slice_outputs': {},
                'temp_files': {}
            },
            'llm_conversation_state': {
                'messages': [],
                'tool_call_history': [],
                'last_response': None,
                'iteration_count': 0,
                'all_results': [],
                'fields_data': {}
            },
            'metadata': metadata or {}
        }

        self._active_checkpoints[checkpoint_id] = data
        self._save_checkpoint(checkpoint_id)
        return checkpoint_id

    def _get_checkpoint_path(self, checkpoint_id: str) -> str:
        """获取 checkpoint 文件路径。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            str: checkpoint 文件路径。

        Raises:
            Exception: 路径构造失败时向上抛出。
        """
        return os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")

    def _save_checkpoint(self, checkpoint_id: str) -> None:
        """保存 checkpoint 数据到磁盘。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            None

        Raises:
            Exception: 文件写入异常未被内部拦截时向上抛出。
        """
        with self._file_lock:
            data = self._active_checkpoints.get(checkpoint_id)
            if not data:
                return
            data['updated_at'] = datetime.now().isoformat()
            path = self._get_checkpoint_path(checkpoint_id)
            temp_path = path + ".tmp"
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                shutil.move(temp_path, path)
            except Exception as e:
                print(f"Failed to save {checkpoint_id}: {e}")
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

    def load_checkpoint(self, checkpoint_id: str) -> Optional[dict[str, Any]]:
        """加载 checkpoint 数据。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            Optional[dict[str, Any]]: checkpoint 数据。

        Raises:
            Exception: 文件读取异常未被内部拦截时向上抛出。
        """
        if checkpoint_id in self._active_checkpoints:
            return self._active_checkpoints[checkpoint_id]

        path = self._get_checkpoint_path(checkpoint_id)
        if not os.path.exists(path):
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._active_checkpoints[checkpoint_id] = data
            return data
        except Exception as e:
            print(f"Failed to load {checkpoint_id}: {e}")
            return None

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
        """更新 checkpoint 进度。

        Args:
            checkpoint_id: checkpoint 标识。
            current_step: 当前步骤。
            total_steps: 总步骤数。
            current_phase: 当前阶段。
            completed_items: 已完成项。
            failed_items: 失败项。
            pending_items: 待处理项。

        Returns:
            None

        Raises:
            Exception: checkpoint 保存失败时向上抛出。
        """
        data = self._active_checkpoints.get(checkpoint_id)
        if not data:
            return
        prog = data['progress']
        if current_step is not None:
            prog['current_step'] = current_step
        if total_steps is not None:
            prog['total_steps'] = total_steps
        if current_phase is not None:
            prog['current_phase'] = current_phase
        if completed_items is not None:
            prog['completed_items'] = completed_items
        if failed_items is not None:
            prog['failed_items'] = failed_items
        if pending_items is not None:
            prog['pending_items'] = pending_items
        self._save_checkpoint(checkpoint_id)

    def save_slice_result(
        self,
        checkpoint_id: str,
        slice_index: int,
        content: str,
        status: str = "completed",
    ) -> str | None:
        """保存切片结果文件。

        Args:
            checkpoint_id: checkpoint 标识。
            slice_index: 切片索引。
            content: 切片内容。
            status: 切片状态。

        Returns:
            str | None: 切片临时文件路径。

        Raises:
            Exception: 切片写入异常未被内部拦截时向上抛出。
        """
        data = self._active_checkpoints.get(checkpoint_id)
        if not data:
            return None
        ckpt_dir = os.path.join(self.temp_dir, checkpoint_id)
        slice_file = os.path.join(ckpt_dir, f"slice_{slice_index}.dat")
        try:
            with open(slice_file, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"Failed to save slice {slice_index}: {e}")
            return None

        data['intermediate_results']['slice_outputs'][str(slice_index)] = {
            'temp_file': slice_file,
            'status': status
        }
        self._save_checkpoint(checkpoint_id)
        return slice_file

    def mark_slice_completed(self, checkpoint_id: str, slice_index: int) -> None:
        """标记切片已完成。

        Args:
            checkpoint_id: checkpoint 标识。
            slice_index: 切片索引。

        Returns:
            None

        Raises:
            Exception: checkpoint 保存失败时向上抛出。
        """
        with self._file_lock:
            data = self._active_checkpoints.get(checkpoint_id)
            if not data:
                return
            prog = data.get('progress', {})
            completed = prog.setdefault('completed_items', [])
            pending = prog.setdefault('pending_items', [])
            if slice_index not in completed:
                completed.append(slice_index)
            prog['pending_items'] = [i for i in pending if i != slice_index]
            self._save_checkpoint(checkpoint_id)

    def get_slice_result(self, checkpoint_id: str, slice_index: int) -> Optional[str]:
        """读取切片结果内容。

        Args:
            checkpoint_id: checkpoint 标识。
            slice_index: 切片索引。

        Returns:
            Optional[str]: 切片内容。

        Raises:
            Exception: 文件读取异常未被内部拦截时向上抛出。
        """
        data = self._active_checkpoints.get(checkpoint_id)
        if not data:
            return None
        slice_info = data['intermediate_results']['slice_outputs'].get(str(slice_index))
        if not slice_info:
            return None
        temp_file = slice_info.get('temp_file')
        if not temp_file or not os.path.exists(temp_file):
            return None
        try:
            with open(temp_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

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
        """保存 LLM 会话状态。

        Args:
            checkpoint_id: checkpoint 标识。
            messages: 消息列表。
            last_response: 最近一次模型响应。
            iteration_count: 迭代次数。
            tool_call_history: 工具调用历史。
            all_results: 累积结果。
            fields_data: 字段数据。
            extra_data: 额外状态字段。

        Returns:
            None

        Raises:
            Exception: checkpoint 保存失败时向上抛出。
        """
        data = self._active_checkpoints.get(checkpoint_id)
        if not data:
            return
        state = data['llm_conversation_state']
        state['messages'] = messages
        if last_response is not None:
            state['last_response'] = self._serialize_llm_response(last_response)
        if iteration_count is not None:
            state['iteration_count'] = iteration_count
        if tool_call_history is not None:
            state['tool_call_history'] = tool_call_history
        if all_results is not None:
            state['all_results'] = all_results
        if fields_data is not None:
            state['fields_data'] = fields_data
        if extra_data:
            state.update(extra_data)
        self._save_checkpoint(checkpoint_id)

    def load_llm_state(self, checkpoint_id: str) -> Optional[dict[str, Any]]:
        """加载 LLM 会话状态。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            Optional[dict[str, Any]]: LLM 会话状态。

        Raises:
            Exception: 状态读取失败时向上抛出。
        """
        data = self._active_checkpoints.get(checkpoint_id)
        if not data:
            return None
        return data['llm_conversation_state']

    def _serialize_llm_response(self, response: Any) -> Optional[dict[str, Any]]:
        """序列化模型响应对象。

        Args:
            response: 模型响应对象。

        Returns:
            Optional[dict[str, Any]]: 可持久化的响应数据。

        Raises:
            Exception: 序列化异常未被内部拦截时向上抛出。
        """
        if response is None:
            return None
        try:
            serialized = {
                'id': getattr(response, 'id', None),
                'model': getattr(response, 'model', None),
                'choices': []
            }
            if hasattr(response, 'choices'):
                for choice in response.choices:
                    choice_data = {
                        'index': getattr(choice, 'index', 0),
                        'finish_reason': getattr(choice, 'finish_reason', None),
                        'message': {
                            'role': getattr(choice.message, 'role', 'assistant'),
                            'content': getattr(choice.message, 'content', None),
                        }
                    }
                    if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                        tool_calls = []
                        for tc in choice.message.tool_calls:
                            tc_data = {
                                'id': tc.id if hasattr(tc, 'id') else tc.get('id'),
                                'type': tc.type if hasattr(tc, 'type') else tc.get('type', 'function'),
                                'function': {
                                    'name': tc.function.name if hasattr(tc, 'function') else tc['function']['name'],
                                    'arguments': tc.function.arguments if hasattr(tc, 'function') else tc['function']['arguments']
                                }
                            }
                            tool_calls.append(tc_data)
                        choice_data['message']['tool_calls'] = tool_calls
                    serialized['choices'].append(choice_data)
            return serialized
        except Exception as e:
            print(f"Failed to serialize LLM response: {e}")
            return None

    def mark_completed(
        self,
        checkpoint_id: str,
        final_output_path: str | None = None,
    ) -> None:
        """标记任务完成。

        Args:
            checkpoint_id: checkpoint 标识。
            final_output_path: 最终输出路径。

        Returns:
            None

        Raises:
            Exception: checkpoint 保存失败时向上抛出。
        """
        data = self._active_checkpoints.get(checkpoint_id)
        if not data:
            return
        data['status'] = 'completed'
        if final_output_path:
            data['intermediate_results']['final_output_path'] = final_output_path
        self._save_checkpoint(checkpoint_id)

    def mark_failed(self, checkpoint_id: str, error_message: str) -> None:
        """标记任务失败。

        Args:
            checkpoint_id: checkpoint 标识。
            error_message: 错误消息。

        Returns:
            None

        Raises:
            Exception: checkpoint 保存失败时向上抛出。
        """
        data = self._active_checkpoints.get(checkpoint_id)
        if not data:
            return
        data['status'] = 'failed'
        data['progress']['error_message'] = error_message
        self._save_checkpoint(checkpoint_id)

    def list_checkpoints(
        self,
        task_type: str | None = None,
        status: str | None = None,
    ) -> List[dict[str, Any]]:
        """列出 checkpoint 概览。

        Args:
            task_type: 任务类型过滤条件。
            status: 状态过滤条件。

        Returns:
            List[dict[str, Any]]: checkpoint 概览列表。

        Raises:
            Exception: 列表读取失败时向上抛出。
        """
        checkpoints = []
        if not os.path.exists(self.checkpoint_dir):
            return checkpoints
        for filename in os.listdir(self.checkpoint_dir):
            if not filename.endswith('.json'):
                continue
            checkpoint_id = filename[:-5]
            data = self.load_checkpoint(checkpoint_id)
            if not data:
                continue
            if task_type and data['task_type'] != task_type:
                continue
            if status and data['status'] != status:
                continue
            checkpoints.append({
                'checkpoint_id': data['checkpoint_id'],
                'task_type': data['task_type'],
                'status': data['status'],
                'created_at': data['created_at'],
                'updated_at': data['updated_at'],
                'progress': data['progress'],
                'input_params': {
                    k: v for k, v in data.get('input_params', {}).items()
                    if k != 'vndb_data'
                }
            })
        return sorted(checkpoints, key=lambda x: x['updated_at'], reverse=True)

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """删除 checkpoint 及其临时文件。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            bool: 是否删除成功。

        Raises:
            Exception: 删除异常未被内部拦截时向上抛出。
        """
        path = self._get_checkpoint_path(checkpoint_id)
        temp_path = os.path.join(self.temp_dir, checkpoint_id)
        has_record = (
            checkpoint_id in self._active_checkpoints
            or os.path.exists(path)
            or os.path.exists(temp_path)
        )
        if not has_record:
            return False

        self._cleanup_temp_files(checkpoint_id)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                return False
        self._active_checkpoints.pop(checkpoint_id, None)
        return True

    def _cleanup_temp_files(self, checkpoint_id: str) -> None:
        """清理 checkpoint 临时目录。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            None

        Raises:
            Exception: 清理异常未被内部拦截时向上抛出。
        """
        ckpt_dir = os.path.join(self.temp_dir, checkpoint_id)
        if os.path.exists(ckpt_dir):
            try:
                shutil.rmtree(ckpt_dir, ignore_errors=True)
            except Exception:
                pass

    def get_temp_dir(self, checkpoint_id: str) -> str:
        """获取并确保存在临时目录。

        Args:
            checkpoint_id: checkpoint 标识。

        Returns:
            str: 临时目录路径。

        Raises:
            Exception: 目录创建失败时向上抛出。
        """
        ckpt_dir = os.path.join(self.temp_dir, checkpoint_id)
        os.makedirs(ckpt_dir, exist_ok=True)
        return ckpt_dir
