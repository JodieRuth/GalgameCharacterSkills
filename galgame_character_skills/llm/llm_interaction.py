"""LLM 交互模块，封装消息构造、completion 调用与工具循环入口。"""

from typing import Any

from ..gateways.tool_gateway import DefaultToolGateway
from .transport import CompletionTransport
from .runtime import LLMRequestRuntime
from .provider_config import normalize_model_name, build_completion_kwargs

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
        self.runtime = runtime or self._runtime_cls()
    
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
    def build_runtime(cls, total_requests: int = 0) -> Any:
        """构造请求级运行时实例。"""
        return cls._runtime_cls(total_requests=total_requests)

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
        model = normalize_model_name(self.modelname, self.baseurl)
        self._log_request_start(model=model, messages=messages, tools=tools, use_counter=use_counter)
        kwargs = build_completion_kwargs(
            model=model,
            messages=messages,
            tools=tools,
            apikey=self.apikey,
            baseurl=self.baseurl,
        )
        
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
