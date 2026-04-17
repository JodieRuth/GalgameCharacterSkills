from .tool_handler import ToolHandler


class ToolGateway:
    def handle_tool_call(self, tool_call):
        raise NotImplementedError

    def parse_llm_json_response(self, content):
        raise NotImplementedError

    def merge_lorebook_entries(self, entries):
        raise NotImplementedError

    def build_lorebook_entries(self, merged_entries, start_id=0):
        raise NotImplementedError

    def fill_json_template(self, template_path, output_path, field_mappings):
        raise NotImplementedError


class DefaultToolGateway(ToolGateway):
    def handle_tool_call(self, tool_call):
        return ToolHandler.handle_tool_call(tool_call)

    def parse_llm_json_response(self, content):
        return ToolHandler.parse_llm_json_response(content)

    def merge_lorebook_entries(self, entries):
        return ToolHandler.merge_lorebook_entries(entries)

    def build_lorebook_entries(self, merged_entries, start_id=0):
        return ToolHandler.build_lorebook_entries(merged_entries, start_id=start_id)

    def fill_json_template(self, template_path, output_path, field_mappings):
        return ToolHandler.fill_json_template(template_path, output_path, field_mappings)


__all__ = ["ToolGateway", "DefaultToolGateway"]
