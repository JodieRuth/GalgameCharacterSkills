"""LLM 网关模块，负责创建和提供默认的 LLM 交互客户端。"""

from typing import Any

from ..llm.factory import build_llm_client
from ..llm import LLMInteraction


class LLMGateway:
    def create_client(
        self,
        config: dict[str, Any] | None = None,
        request_runtime: Any = None,
    ) -> Any:
        """创建 LLM 客户端。

        Args:
            config: LLM 配置。
            request_runtime: 请求级运行时对象。

        Returns:
            Any: LLM 客户端实例。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError

    def create_request_runtime(self, total: int = 0) -> Any:
        """创建请求级运行时。

        Args:
            total: 总请求数。

        Returns:
            Any: 请求级运行时实例。

        Raises:
            NotImplementedError: 子类未实现时抛出。
        """
        raise NotImplementedError


class DefaultLLMGateway(LLMGateway):
    def create_client(
        self,
        config: dict[str, Any] | None = None,
        request_runtime: Any = None,
    ) -> Any:
        """创建默认 LLM 客户端。

        Args:
            config: LLM 配置。
            request_runtime: 请求级运行时对象。

        Returns:
            Any: LLM 客户端实例。

        Raises:
            Exception: 客户端创建失败时向上抛出。
        """
        return build_llm_client(config, request_runtime=request_runtime)

    def create_request_runtime(self, total: int = 0) -> Any:
        """创建默认请求运行时。

        Args:
            total: 总请求数。

        Returns:
            Any: 请求级运行时实例。

        Raises:
            Exception: 请求数设置失败时向上抛出。
        """
        return LLMInteraction.build_runtime(total_requests=total)


__all__ = ["LLMGateway", "DefaultLLMGateway"]
