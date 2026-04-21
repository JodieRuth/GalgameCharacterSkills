"""LLM 网关模块，负责创建和提供默认的 LLM 交互客户端。"""

from ..utils.llm_factory import build_llm_client
from ..llm import LLMInteraction


class LLMGateway:
    def create_client(self, config=None):
        raise NotImplementedError

    def set_total_requests(self, total):
        raise NotImplementedError


class DefaultLLMGateway(LLMGateway):
    def create_client(self, config=None):
        return build_llm_client(config)

    def set_total_requests(self, total):
        LLMInteraction.set_total_requests(total)


__all__ = ["LLMGateway", "DefaultLLMGateway"]
