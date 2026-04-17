from ..utils.tool_handler import ToolHandler


class ToolGateway:
    def handle_tool_call(self, tool_call):
        raise NotImplementedError

    def parse_llm_json_response(self, content):
        raise NotImplementedError


class DefaultToolGateway(ToolGateway):
    def handle_tool_call(self, tool_call):
        return ToolHandler.handle_tool_call(tool_call)

    def parse_llm_json_response(self, content):
        return ToolHandler.parse_llm_json_response(content)


__all__ = ["ToolGateway", "DefaultToolGateway"]
