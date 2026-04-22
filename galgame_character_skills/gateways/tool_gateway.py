"""工具网关模块，提供 tool call 解析与执行器实例的抽象入口。"""

from typing import Any

from ..tools import ToolHandler


class ToolGateway:
    def handle_tool_call(self, tool_call: Any) -> Any:
        """执行单个工具调用。

        Args:
            tool_call: 工具调用对象。

        Returns:
            Any: 工具执行结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def parse_llm_json_response(self, content: str) -> dict[str, Any] | None:
        """解析模型返回的 JSON 文本。

        Args:
            content: 模型返回内容。

        Returns:
            dict[str, Any] | None: 解析后的 JSON 数据。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def merge_lorebook_entries(self, entries: list[Any]) -> list[Any]:
        """合并 lorebook 条目。

        Args:
            entries: lorebook 条目列表。

        Returns:
            list[Any]: 合并后的条目列表。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def build_lorebook_entries(self, merged_entries: list[Any], start_id: int = 0) -> list[Any]:
        """构造 lorebook 条目列表。

        Args:
            merged_entries: 合并后的条目列表。
            start_id: 起始编号。

        Returns:
            list[Any]: 构造后的条目列表。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def fill_json_template(
        self,
        template_path: str,
        output_path: str,
        field_mappings: dict[str, Any],
    ) -> Any:
        """填充 JSON 模板文件。

        Args:
            template_path: 模板路径。
            output_path: 输出路径。
            field_mappings: 字段映射。

        Returns:
            Any: 模板填充结果。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError


class DefaultToolGateway(ToolGateway):
    def handle_tool_call(self, tool_call: Any) -> Any:
        """执行默认工具调用。"""
        return ToolHandler.handle_tool_call(tool_call)

    def parse_llm_json_response(self, content: str) -> dict[str, Any] | None:
        """解析模型返回的 JSON 文本。"""
        return ToolHandler.parse_llm_json_response(content)

    def merge_lorebook_entries(self, entries: list[Any]) -> list[Any]:
        """合并 lorebook 条目。"""
        return ToolHandler.merge_lorebook_entries(entries)

    def build_lorebook_entries(self, merged_entries: list[Any], start_id: int = 0) -> list[Any]:
        """构造 lorebook 条目列表。"""
        return ToolHandler.build_lorebook_entries(merged_entries, start_id=start_id)

    def fill_json_template(
        self,
        template_path: str,
        output_path: str,
        field_mappings: dict[str, Any],
    ) -> Any:
        """填充 JSON 模板文件。"""
        return ToolHandler.fill_json_template(template_path, output_path, field_mappings)


__all__ = ["ToolGateway", "DefaultToolGateway"]
