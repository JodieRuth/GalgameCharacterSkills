"""LLM 交互模块，封装消息构造、completion 调用与工具循环入口。"""

import json
from typing import Any

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

def _format_vndb_section(
    vndb_data: dict[str, Any] | None,
    title: str,
    bullet: str = "-",
) -> str:
    """格式化 VNDB 信息段落。

    Args:
        vndb_data: VNDB 数据。
        title: 段落标题。
        bullet: 列表前缀。

    Returns:
        str: 格式化后的段落文本。

    Raises:
        Exception: 文本构造失败时向上抛出。
    """
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

    def __init__(
        self,
        tool_gateway: Any = None,
        transport: Any = None,
        runtime: Any = None,
    ) -> None:
        """初始化 LLM 交互客户端。

        Args:
            tool_gateway: 工具网关。
            transport: 传输层实现。
            runtime: 运行时记录器。

        Returns:
            None

        Raises:
            Exception: 初始化失败时向上抛出。
        """
        self.baseurl = ""
        self.modelname = ""
        self.apikey = ""
        self.max_retries = 3
        self.tool_gateway = tool_gateway or DefaultToolGateway()
        self.transport = transport or CompletionTransport()
        self.runtime = runtime or self._runtime_cls
    
    def set_config(
        self,
        baseurl: str,
        modelname: str,
        apikey: str,
        max_retries: int | None = None,
    ) -> None:
        """设置客户端配置。

        Args:
            baseurl: 接口基地址。
            modelname: 模型名。
            apikey: API Key。
            max_retries: 最大重试次数。

        Returns:
            None

        Raises:
            Exception: 配置设置失败时向上抛出。
        """
        self.baseurl = baseurl
        self.modelname = modelname
        self.apikey = apikey
        if max_retries is not None and max_retries > 0:
            self.max_retries = max_retries
    
    @classmethod
    def set_total_requests(cls, total: int) -> None:
        """设置任务总请求数。"""
        cls._runtime_cls.set_total_requests(total)

    def _normalize_model_name(self) -> str:
        """规范化模型名称。"""
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

    def _build_completion_kwargs(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """构造 completion 请求参数。"""
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

    def _log_request_start(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        use_counter: bool,
    ) -> None:
        """记录请求开始日志。"""
        self.runtime.log_request_start(
            model=model,
            baseurl=self.baseurl,
            apikey=self.apikey,
            messages=messages,
            tools=tools,
            use_counter=use_counter,
        )

    def _log_request_success(self, use_counter: bool) -> None:
        """记录请求成功日志。"""
        self.runtime.log_request_success(use_counter=use_counter)

    def _log_response_preview(self, response: Any) -> None:
        """记录响应预览日志。"""
        self.runtime.log_response_preview(response)

    def _log_request_failed(self, use_counter: bool) -> None:
        """记录请求失败日志。"""
        self.runtime.log_request_failed(use_counter=use_counter)
    
    def send_message(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_retries: int | None = None,
        use_counter: bool = True,
    ) -> Any:
        """发送一次模型请求。

        Args:
            messages: 消息列表。
            tools: 工具定义列表。
            max_retries: 最大重试次数。
            use_counter: 是否使用计数器。

        Returns:
            Any: 模型响应对象，失败时返回 None。

        Raises:
            Exception: 请求发送或回调执行失败时向上抛出。
        """
        if max_retries is None:
            max_retries = self.max_retries
        model = self._normalize_model_name()
        self._log_request_start(model=model, messages=messages, tools=tools, use_counter=use_counter)
        kwargs = self._build_completion_kwargs(model=model, messages=messages, tools=tools)
        
        print(f"[LLM] Attempt 1/{max_retries}")

        def _on_attempt_failed(attempt: int, error: Exception, retries: int) -> None:
            print(f"[LLM] Attempt {attempt + 1} failed: {error}")

        def _on_retry_wait(wait_time: int, attempt: int, retries: int) -> None:
            print(f"[LLM] Retrying in {wait_time} seconds...")

        def _on_success(response: Any) -> None:
            self._log_request_success(use_counter=use_counter)
            self._log_response_preview(response)

        def _on_final_failure(error: Exception) -> None:
            self._log_request_failed(use_counter=use_counter)

        return self.transport.complete_with_retry(
            kwargs=kwargs,
            max_retries=max_retries,
            on_attempt_failed=_on_attempt_failed,
            on_retry_wait=_on_retry_wait,
            on_success=_on_success,
            on_final_failure=_on_final_failure,
        )
    
    def get_tool_response(self, response: Any) -> list[Any] | None:
        """提取模型响应中的工具调用。"""
        if response and hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'tool_calls'):
                return choice.message.tool_calls
        return None
    
    def summarize_content(
        self,
        content: str,
        role_name: str,
        instruction: str,
        output_file_path: str,
        output_language: str = "",
        vndb_data: dict[str, Any] | None = None,
    ) -> Any:
        """执行文本归纳请求。"""
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
    
    def summarize_content_for_chara_card(
        self,
        content: str,
        role_name: str,
        instruction: str,
        output_file_path: str,
        output_language: str = "",
        vndb_data: dict[str, Any] | None = None,
    ) -> Any:
        """执行角色卡分析归纳请求。"""
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
    
    def generate_skills_folder_init(
        self,
        summaries: str,
        role_name: str,
        output_language: str = "",
        vndb_data: dict[str, Any] | None = None,
        output_root_dir: str = "",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """构造技能包初始化消息和工具定义。"""
        messages, tools = build_generate_skills_folder_init_payload(
            summaries=summaries,
            role_name=role_name,
            output_root_dir=output_root_dir,
            output_language=output_language,
            vndb_data=vndb_data,
            lang_names=LANG_NAMES,
            format_vndb_section=_format_vndb_section,
        )
        return messages, tools

    def compress_content_with_llm(
        self,
        group_files_content: dict[str, str],
        group_info: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """构造压缩请求消息和工具定义。"""
        messages, tools = build_compress_content_payload(
            group_files_content=group_files_content,
            group_info=group_info,
        )
        return messages, tools

    def generate_character_card_with_tools(
        self,
        role_name: str,
        all_analyses: list[dict[str, Any]],
        all_lorebook_entries: list[Any],
        output_path: str,
        creator: str = "",
        vndb_data: dict[str, Any] | None = None,
        output_language: str = "",
        checkpoint_id: str | None = None,
        ckpt_messages: list[dict[str, Any]] | None = None,
        ckpt_fields_data: dict[str, Any] | None = None,
        ckpt_iteration_count: int | None = None,
        save_llm_state_fn: Any = None,
    ) -> dict[str, Any]:
        """执行角色卡生成流程。"""
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
            save_llm_state_fn=save_llm_state_fn,
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
    
    def _integrate_analyses(
        self,
        role_name: str,
        all_analyses: list[dict[str, Any]],
        vndb_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """整合多份角色分析结果。"""
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
