"""LLM client factory functions."""

from typing import Any

from ..llm import LLMInteraction


def build_llm_client(
    config: dict[str, Any] | None = None,
    request_runtime: Any = None,
) -> LLMInteraction:
    """构建 LLM 交互客户端。

    Args:
        config: LLM 配置字典。
        request_runtime: 请求级运行时对象。

    Returns:
        LLMInteraction: 已完成配置注入的客户端实例。

    Raises:
        Exception: 客户端构造或配置失败时向上抛出。
    """
    config = config or {}
    baseurl = config.get('baseurl', '')
    modelname = config.get('modelname', '')
    apikey = config.get('apikey', '')
    max_retries = config.get('max_retries', 0) or None
    client = LLMInteraction(runtime=request_runtime)
    if baseurl or modelname or apikey:
        client.set_config(baseurl, modelname, apikey, max_retries=max_retries)
    return client
