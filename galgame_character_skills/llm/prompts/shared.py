"""LLM prompt 共享片段模块。"""

from typing import Any


def build_write_file_tool(content_description: str) -> list[dict[str, Any]]:
    """构造 write_file 工具定义。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write file to local disk",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "File path",
                        },
                        "content": {
                            "type": "string",
                            "description": content_description,
                        },
                    },
                    "required": ["file_path", "content"],
                },
            },
        }
    ]


__all__ = ["build_write_file_tool"]
