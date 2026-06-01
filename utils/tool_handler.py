import os
import json
import re

class ToolHandler:
    @staticmethod
    def write_file(file_path, content):
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
    def parse_tool_arguments_list(arguments_str):
        if not isinstance(arguments_str, str):
            return [arguments_str]

        decoder = json.JSONDecoder()
        position = 0
        parsed = []
        length = len(arguments_str)

        while position < length:
            while position < length and arguments_str[position].isspace():
                position += 1
            if position >= length:
                break
            value, end = decoder.raw_decode(arguments_str, position)
            parsed.append(value)
            position = end

        return parsed

    @staticmethod
    def parse_tool_arguments(arguments_str):
        parsed = ToolHandler.parse_tool_arguments_list(arguments_str)
        return parsed[0] if parsed else {}

    @staticmethod
    def handle_tool_call(tool_call):
        if hasattr(tool_call, 'function'):
            function_name = tool_call.function.name
            arguments_str = tool_call.function.arguments
        else:
            function_name = tool_call['function']['name']
            arguments_str = tool_call['function']['arguments']
        
        try:
            arguments_list = ToolHandler.parse_tool_arguments_list(arguments_str)
        except json.JSONDecodeError as e:
            preview = str(arguments_str)[:500].replace('\n', '\\n')
            return f"Invalid tool arguments JSON: {e}; preview={preview}"
        
        results = []
        for arguments in arguments_list:
            if function_name == 'write_file':
                file_path = arguments.get('file_path') if isinstance(arguments, dict) else None
                content = arguments.get('content') if isinstance(arguments, dict) else None
                if file_path and content:
                    results.append(ToolHandler.write_file(file_path, content))
                else:
                    results.append("Missing required parameters")
            else:
                results.append(f"Unknown tool: {function_name}")
        return "\n".join(results) if results else "No tool arguments"

    @staticmethod
    def fill_json_template(template_path, output_path, field_mappings):
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
    def build_lorebook_entries(entries_list, start_id=0):
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
    def merge_lorebook_entries(entries_list):
        merged = {}
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
    def parse_llm_json_response(content):
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
