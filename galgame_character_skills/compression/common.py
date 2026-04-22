"""压缩子系统公共辅助模块。"""

import json
import os
import shutil
import tempfile
from typing import Any


def create_temp_workspace(
    *,
    checkpoint_id: str | None,
    ckpt_manager: Any,
    workspace_name: str,
) -> str:
    """创建压缩流程的临时工作目录。

    Args:
        checkpoint_id: checkpoint 标识。
        ckpt_manager: checkpoint 管理器。
        workspace_name: 工作目录名称。

    Returns:
        str: 临时工作目录路径。

    Raises:
        Exception: 目录创建失败时向上抛出。
    """
    if checkpoint_id:
        ckpt_temp_dir = ckpt_manager.get_temp_dir(checkpoint_id)
        temp_dir = os.path.join(ckpt_temp_dir, workspace_name)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_base_dir = os.path.join(project_root, "temp")
    os.makedirs(temp_base_dir, exist_ok=True)
    return tempfile.mkdtemp(prefix=f"{workspace_name}_", dir=temp_base_dir)


def cleanup_temp_workspace(temp_dir: str) -> None:
    """清理临时工作目录。

    Args:
        temp_dir: 临时工作目录路径。

    Returns:
        None

    Raises:
        Exception: 清理异常未被内部拦截时向上抛出。
    """
    try:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp workspace: {temp_dir}")
    except Exception as e:
        print(f"Warning: Failed to cleanup temp dir: {e}")


def build_group_info(group_index: int, total_groups: int, file_count: int) -> dict[str, int]:
    """构造压缩分组信息。

    Args:
        group_index: 分组索引。
        total_groups: 总分组数。
        file_count: 当前分组文件数。

    Returns:
        dict[str, int]: 分组信息字典。

    Raises:
        Exception: 分组信息构造失败时向上抛出。
    """
    return {
        "group_index": group_index,
        "total_groups": total_groups,
        "file_count": file_count,
    }


def append_tool_exchange_messages(
    messages: list[dict[str, Any]],
    message: Any,
    tool_results: list[dict[str, Any]],
) -> None:
    """向消息列表追加工具调用交换记录。

    Args:
        messages: 会话消息列表。
        message: 助手消息对象。
        tool_results: 工具执行结果列表。

    Returns:
        None

    Raises:
        Exception: 消息构造失败时向上抛出。
    """
    messages.append(
        {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": tc.id if hasattr(tc, "id") else tc.get("id"),
                    "type": "function",
                    "function": {
                        "name": tc.function.name if hasattr(tc, "function") else tc["function"]["name"],
                        "arguments": tc.function.arguments if hasattr(tc, "function") else tc["function"]["arguments"],
                    },
                }
                for tc in message.tool_calls
            ],
        }
    )

    for result in tool_results:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": result["tool_call_id"],
                "content": json.dumps({"status": "success", "message": result["result"]}),
            }
        )
