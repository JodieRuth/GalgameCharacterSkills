import json
from ..gateways.tool_gateway import DefaultToolGateway
from .transport import CompletionTransport
from .runtime import LLMRequestRuntime
from .tool_loop import run_character_card_tool_loop
from .task_flows import (
    build_write_field_tools,
    build_initial_character_card_fields,
    apply_checkpoint_fields,
    build_character_card_messages,
    build_character_card_template_path,
    build_character_card_field_mappings,
    build_character_card_success_result,
)
from .prompts import (
    build_summarize_content_payload,
    build_summarize_chara_card_payload,
    build_generate_skills_folder_init_payload,
    build_compress_content_payload,
)
from ..utils.prompt_builders import (
    build_character_card_language_instruction,
    build_character_card_system_prompt,
    build_integrate_analyses_system_prompt,
    build_integrate_analyses_user_prompt,
)

LANG_NAMES = {"zh": "中文", "en": "English", "ja": "日本語"}

def _format_vndb_section(vndb_data, title, bullet="-"):
    if not vndb_data:
        return ""

    entries = []
    field_map = [
        ("name", "Name"),
        ("original_name", "Original Name"),
        ("aliases", "Aliases"),
        ("description", "Description"),
        ("age", "Age"),
        ("birthday", "Birthday"),
        ("blood_type", "Blood Type"),
        ("height", "Height"),
        ("weight", "Weight"),
        ("traits", "Traits"),
        ("vns", "Visual Novels"),
    ]

    for key, label in field_map:
        value = vndb_data.get(key)
        if not value:
            continue
        if key == "aliases" and isinstance(value, list):
            value = ", ".join(value)
        elif key == "traits" and isinstance(value, list):
            value = ", ".join(value)
        elif key == "vns" and isinstance(value, list):
            value = ", ".join(value[:3])
        elif key == "height":
            value = f"{value}cm"
        elif key == "weight":
            value = f"{value}kg"
        prefix = f"{bullet} " if bullet else ""
        entries.append(f"{prefix}{label}: {value}")

    if vndb_data.get('bust') and vndb_data.get('waist') and vndb_data.get('hips'):
        prefix = f"{bullet} " if bullet else ""
        entries.append(f"{prefix}Measurements: {vndb_data['bust']}-{vndb_data['waist']}-{vndb_data['hips']}cm")

    if not entries:
        return ""

    return f"\n\n{title}\n" + "\n".join(entries) + "\n"

class LLMInteraction:
    _runtime_cls = LLMRequestRuntime

    def __init__(self, tool_gateway=None, transport=None, runtime=None):
        self.baseurl = ""
        self.modelname = ""
        self.apikey = ""
        self.max_retries = 3
        self.tool_gateway = tool_gateway or DefaultToolGateway()
        self.transport = transport or CompletionTransport()
        self.runtime = runtime or self._runtime_cls
    
    def set_config(self, baseurl, modelname, apikey, max_retries=None):
        self.baseurl = baseurl
        self.modelname = modelname
        self.apikey = apikey
        if max_retries is not None and max_retries > 0:
            self.max_retries = max_retries
    
    @classmethod
    def set_total_requests(cls, total):
        cls._runtime_cls.set_total_requests(total)

    def _normalize_model_name(self):
        model = self.modelname
        baseurl = self.baseurl.lower() if self.baseurl else ''

        if model and '/' not in model:
            if 'deepseek' in baseurl:
                return f"deepseek/{model}"
            if 'anthropic' in baseurl or 'claude' in baseurl:
                return f"anthropic/{model}"
            if 'gemini' in baseurl or 'google' in baseurl:
                return f"google/{model}"
            return f"openai/{model}"
        return model

    def _build_completion_kwargs(self, model, messages, tools):
        kwargs = {
            "model": model,
            "messages": messages,
            "timeout": 300
        }

        if 'google' in model or 'gemini' in model:
            kwargs["safety_settings"] = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if self.apikey:
            kwargs["api_key"] = self.apikey
        if self.baseurl:
            kwargs["api_base"] = self.baseurl
        return kwargs

    def _log_request_start(self, model, messages, tools, use_counter):
        self.runtime.log_request_start(
            model=model,
            baseurl=self.baseurl,
            apikey=self.apikey,
            messages=messages,
            tools=tools,
            use_counter=use_counter,
        )

    def _log_request_success(self, use_counter):
        self.runtime.log_request_success(use_counter=use_counter)

    def _log_response_preview(self, response):
        self.runtime.log_response_preview(response)

    def _log_request_failed(self, use_counter):
        self.runtime.log_request_failed(use_counter=use_counter)
    
    def send_message(self, messages, tools=None, max_retries=None, use_counter=True):
        if max_retries is None:
            max_retries = self.max_retries
        model = self._normalize_model_name()
        self._log_request_start(model=model, messages=messages, tools=tools, use_counter=use_counter)
        kwargs = self._build_completion_kwargs(model=model, messages=messages, tools=tools)
        
        print(f"[LLM] Attempt 1/{max_retries}")

        def _on_attempt_failed(attempt, error, retries):
            print(f"[LLM] Attempt {attempt + 1} failed: {error}")

        def _on_retry_wait(wait_time, attempt, retries):
            print(f"[LLM] Retrying in {wait_time} seconds...")

        def _on_success(response):
            self._log_request_success(use_counter=use_counter)
            self._log_response_preview(response)

        def _on_final_failure(error):
            self._log_request_failed(use_counter=use_counter)

        return self.transport.complete_with_retry(
            kwargs=kwargs,
            max_retries=max_retries,
            on_attempt_failed=_on_attempt_failed,
            on_retry_wait=_on_retry_wait,
            on_success=_on_success,
            on_final_failure=_on_final_failure,
        )
    
    def get_tool_response(self, response):
        if response and hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls'):
                return choice.message.tool_calls
        return None
    
    def summarize_content(self, content, role_name, instruction, output_file_path, output_language="", vndb_data=None):
        messages, tools = build_summarize_content_payload(
            content=content,
            role_name=role_name,
            instruction=instruction,
            output_file_path=output_file_path,
            output_language=output_language,
            vndb_data=vndb_data,
            lang_names=LANG_NAMES,
            format_vndb_section=_format_vndb_section,
        )
        return self.send_message(messages, tools)
    
    def summarize_content_for_chara_card(self, content, role_name, instruction, output_file_path, output_language="", vndb_data=None):
        messages, tools = build_summarize_chara_card_payload(
            content=content,
            role_name=role_name,
            instruction=instruction,
            output_file_path=output_file_path,
            output_language=output_language,
            vndb_data=vndb_data,
            lang_names=LANG_NAMES,
            format_vndb_section=_format_vndb_section,
        )
        return self.send_message(messages, tools)
    
    def generate_skills_folder_init(self, summaries, role_name, output_language="", vndb_data=None):
        messages, tools = build_generate_skills_folder_init_payload(
            summaries=summaries,
            role_name=role_name,
            output_language=output_language,
            vndb_data=vndb_data,
            lang_names=LANG_NAMES,
            format_vndb_section=_format_vndb_section,
        )
        return messages, tools

    def compress_content_with_llm(self, group_files_content, group_info):
        messages, tools = build_compress_content_payload(
            group_files_content=group_files_content,
            group_info=group_info,
        )
        return messages, tools

    def generate_character_card_with_tools(self, role_name, all_analyses, all_lorebook_entries, output_path, creator="", vndb_data=None, output_language="", checkpoint_id=None, ckpt_messages=None, ckpt_fields_data=None, ckpt_iteration_count=None):
        integrated_analysis = self._integrate_analyses(role_name, all_analyses, vndb_data)
        
        vndb_ref = _format_vndb_section(vndb_data, "VNDB REFERENCE DATA (HIGHEST PRIORITY - Use these values as authoritative source for character appearance and basic info)", bullet="")
        
        tools = build_write_field_tools()
        
        merged_entries = self.tool_gateway.merge_lorebook_entries(all_lorebook_entries)
        lorebook_entries = self.tool_gateway.build_lorebook_entries(merged_entries, start_id=0)
        fields_data = build_initial_character_card_fields(
            role_name=role_name,
            creator=creator,
            vndb_data=vndb_data,
            lorebook_entries=lorebook_entries,
        )

        is_resuming = ckpt_messages is not None and len(ckpt_messages) > 0
        if is_resuming:
            apply_checkpoint_fields(fields_data, ckpt_fields_data)
        
        language_instruction = build_character_card_language_instruction(output_language, LANG_NAMES)
        integrated_analysis_json = json.dumps(integrated_analysis, ensure_ascii=False, indent=2)
        system_prompt = build_character_card_system_prompt(
            role_name=role_name,
            integrated_analysis_json=integrated_analysis_json,
            vndb_ref=vndb_ref,
            language_instruction=language_instruction,
        )

        messages, tool_call_count = build_character_card_messages(
            is_resuming=is_resuming,
            ckpt_messages=ckpt_messages,
            ckpt_iteration_count=ckpt_iteration_count,
            system_prompt=system_prompt,
            role_name=role_name,
        )

        loop_result = run_character_card_tool_loop(
            send_message=self.send_message,
            tool_gateway=self.tool_gateway,
            tools=tools,
            messages=messages,
            fields_data=fields_data,
            checkpoint_id=checkpoint_id,
            initial_tool_call_count=tool_call_count,
            max_tool_calls=50,
        )
        if not loop_result.get("success"):
            return loop_result
        
        template_path = build_character_card_template_path()
        field_mappings = build_character_card_field_mappings(fields_data)
        
        result = self.tool_gateway.fill_json_template(template_path, output_path, field_mappings)
        
        return build_character_card_success_result(
            output_path=output_path,
            fields_data=fields_data,
            result=result,
        )
    
    def _integrate_analyses(self, role_name, all_analyses, vndb_data=None):
        vndb_section = _format_vndb_section(vndb_data, "## VNDB Character Information", bullet="")
        system_prompt = build_integrate_analyses_system_prompt(role_name, vndb_section)
        
        analyses_json = json.dumps(all_analyses, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_integrate_analyses_user_prompt(role_name, analyses_json)}
        ]
        
        response = self.send_message(messages, use_counter=False)
        
        if response and response.choices:
            content = response.choices[0].message.content
            result = self.tool_gateway.parse_llm_json_response(content) or {}
            return result
        return {}
