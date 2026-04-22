"""Tool 调用处理模块，负责解析模型工具调用并执行文件写入。"""

import json
import os
import re
from typing import Any


class ToolHandler:
    @staticmethod
    def write_file(file_path: str, content: str) -> str:
        """写入文本文件。

        Args:
            file_path: 输出文件路径。
            content: 文件内容。

        Returns:
            str: 文件写入结果消息。

        Raises:
            Exception: 文件写入异常未被内部拦截时向上抛出。
        """
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"File written successfully: {file_path}"
        except Exception as e:
            return f"File write failed: {str(e)}"

    @staticmethod
    def handle_tool_call(tool_call: Any) -> str:
        """解析并执行单个工具调用。

        Args:
            tool_call: 工具调用对象或字典。

        Returns:
            str: 工具执行结果消息。

        Raises:
            Exception: 工具参数解析异常未被内部拦截时向上抛出。
        """
        if hasattr(tool_call, 'function'):
            function_name = tool_call.function.name
            arguments_str = tool_call.function.arguments
        else:
            function_name = tool_call['function']['name']
            arguments_str = tool_call['function']['arguments']

        if isinstance(arguments_str, str):
            arguments = json.loads(arguments_str)
        else:
            arguments = arguments_str

        if function_name == 'write_file':
            file_path = arguments.get('file_path')
            content = arguments.get('content')
            if file_path and content:
                return ToolHandler.write_file(file_path, content)
            return "Missing required parameters"
        return f"Unknown tool: {function_name}"

    @staticmethod
    def fill_json_template(
        template_path: str,
        output_path: str,
        field_mappings: dict[str, Any],
    ) -> str:
        """填充 JSON 模板文件。

        Args:
            template_path: 模板文件路径。
            output_path: 输出文件路径。
            field_mappings: 字段映射。

        Returns:
            str: 模板填充结果消息。

        Raises:
            Exception: 模板处理异常未被内部拦截时向上抛出。
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()

            for placeholder, value in field_mappings.items():
                if isinstance(value, (list, dict)):
                    json_value = json.dumps(value, ensure_ascii=False)
                    template = template.replace(placeholder, json_value)

            for placeholder, value in field_mappings.items():
                if isinstance(value, str):
                    escaped_value = json.dumps(value, ensure_ascii=False)
                    template = template.replace(f'"{placeholder}"', escaped_value)

            directory = os.path.dirname(output_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            try:
                parsed = json.loads(template)
                template = json.dumps(parsed, ensure_ascii=False, indent=4)
            except json.JSONDecodeError as e:
                return f"Template filling failed: Generated invalid JSON - {str(e)}"

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(template)

            return f"Character card generated successfully: {output_path}"
        except Exception as e:
            return f"Template filling failed: {str(e)}"

    @staticmethod
    def build_lorebook_entries(entries_list: list[dict[str, Any]], start_id: int = 0) -> list[dict[str, Any]]:
        """构造 lorebook 条目列表。

        Args:
            entries_list: 原始条目列表。
            start_id: 起始编号。

        Returns:
            list[dict[str, Any]]: 格式化后的条目列表。

        Raises:
            Exception: 条目构造失败时向上抛出。
        """
        formatted_entries = []
        for i, entry in enumerate(entries_list):
            formatted_entry = {
                "id": start_id + i,
                "keys": entry.get("keys", []),
                "secondary_keys": [],
                "comment": entry.get("comment", ""),
                "content": entry.get("content", ""),
                "constant": False,
                "selective": True,
                "insertion_order": 100,
                "enabled": True,
                "position": "before_char",
                "use_regex": True,
                "extensions": {
                    "position": 0,
                    "exclude_recursion": False,
                    "display_index": i,
                    "probability": 100,
                    "useProbability": True,
                    "depth": 4,
                    "selectiveLogic": 0,
                    "outlet_name": "",
                    "group": "",
                    "group_override": False,
                    "group_weight": 100,
                    "prevent_recursion": False,
                    "delay_until_recursion": False,
                    "scan_depth": None,
                    "match_whole_words": None,
                    "use_group_scoring": False,
                    "case_sensitive": None,
                    "automation_id": "",
                    "role": 0,
                    "vectorized": False,
                    "sticky": 0,
                    "cooldown": 0,
                    "delay": 0,
                    "match_persona_description": False,
                    "match_character_description": False,
                    "match_character_personality": False,
                    "match_character_depth_prompt": False,
                    "match_scenario": False,
                    "match_creator_notes": False,
                    "triggers": [],
                    "ignore_budget": False
                }
            }
            formatted_entries.append(formatted_entry)
        return formatted_entries

    @staticmethod
    def merge_lorebook_entries(entries_list: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
        """合并 lorebook 条目列表。

        Args:
            entries_list: 多组条目列表。

        Returns:
            list[dict[str, Any]]: 合并后的条目列表。

        Raises:
            Exception: 条目合并失败时向上抛出。
        """
        merged: dict[tuple[str, ...], dict[str, Any]] = {}
        for entries in entries_list:
            for entry in entries:
                key = tuple(sorted(entry.get("keys", [])))
                if key in merged:
                    existing = merged[key]
                    existing["content"] += "\n\n" + entry.get("content", "")
                else:
                    merged[key] = entry.copy()
        return list(merged.values())

    @staticmethod
    def parse_llm_json_response(content: str) -> dict[str, Any] | None:
        """从模型输出中提取 JSON 数据。

        Args:
            content: 模型输出文本。

        Returns:
            dict[str, Any] | None: 解析后的 JSON 数据。

        Raises:
            Exception: JSON 解析异常未被内部拦截时向上抛出。
        """
        if not content:
            return None

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        try:
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
        except (json.JSONDecodeError, AttributeError):
            pass

        try:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except (json.JSONDecodeError, AttributeError):
            pass

        return None
