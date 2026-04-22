"""LLM 请求运行时模块，记录单次任务中的请求计数与统计信息。"""

from typing import Any


class LLMRequestRuntime:
    _request_count = 0
    _total_requests = 0

    @classmethod
    def set_total_requests(cls, total: int) -> None:
        """设置任务总请求数。

        Args:
            total: 总请求数。

        Returns:
            None

        Raises:
            Exception: 计数器设置失败时向上抛出。
        """
        cls._total_requests = total
        cls._request_count = 0

    @classmethod
    def log_request_start(
        cls,
        model: str,
        baseurl: str,
        apikey: str,
        messages: list[Any],
        tools: list[dict[str, Any]] | None,
        use_counter: bool,
    ) -> None:
        """记录请求开始日志。

        Args:
            model: 模型名称。
            baseurl: 接口基地址。
            apikey: API Key。
            messages: 消息列表。
            tools: 工具定义列表。
            use_counter: 是否使用计数器。

        Returns:
            None

        Raises:
            Exception: 日志输出失败时向上抛出。
        """
        api_key_preview = apikey[:10] + "..." if apikey and len(apikey) > 10 else (apikey if apikey else "None")

        if use_counter and cls._total_requests > 0:
            cls._request_count += 1
            current = cls._request_count
            total = cls._total_requests
            print(f"[LLM] Request {current}/{total} - Model: {model}, Base URL: {baseurl}")
        else:
            print(f"[LLM] Request - Model: {model}, Base URL: {baseurl}")

        print(f"[LLM] API Key: {api_key_preview}, Length: {len(apikey) if apikey else 0}")
        print(f"[LLM] Messages count: {len(messages)}, Tools: {'Yes' if tools else 'No'}")

    @classmethod
    def log_request_success(cls, use_counter: bool) -> None:
        """记录请求成功日志。"""
        if use_counter and cls._total_requests > 0:
            current = cls._request_count
            total = cls._total_requests
            remaining = total - current
            print(f"[LLM] Sent {current} requests, {remaining}/{total} remaining")
        else:
            print("[LLM] Request completed")

    @classmethod
    def log_request_failed(cls, use_counter: bool) -> None:
        """记录请求失败日志。"""
        if use_counter and cls._total_requests > 0:
            current = cls._request_count
            total = cls._total_requests
            remaining = total - current
            print(f"[LLM] Sent {current} requests, {remaining}/{total} remaining - Failed")
        else:
            print("[LLM] Request failed")

    @staticmethod
    def log_response_preview(response: Any) -> None:
        """记录响应预览日志。

        Args:
            response: 模型响应对象。

        Returns:
            None

        Raises:
            Exception: 日志输出失败时向上抛出。
        """
        if response and hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            if hasattr(choice, 'message'):
                msg = choice.message
                content_preview = msg.content[:100] + "..." if msg.content and len(msg.content) > 100 else msg.content
                print(f"[LLM] Response content preview: {content_preview}")
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    print(f"[LLM] Tool calls: {len(msg.tool_calls)}")


__all__ = ["LLMRequestRuntime"]
