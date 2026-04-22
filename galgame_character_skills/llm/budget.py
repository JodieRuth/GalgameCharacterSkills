"""LLM context budget helpers."""

from typing import Any

DEFAULT_CONTEXT_LIMIT = 115000
_litellm_module = None


def _get_litellm() -> Any:
    """延迟加载 litellm 模块。

    Args:
        None

    Returns:
        Any: litellm 模块对象。

    Raises:
        ImportError: 模块不可用时抛出。
    """
    global _litellm_module
    if _litellm_module is None:
        import litellm

        _litellm_module = litellm
    return _litellm_module


def get_model_context_limit(model_name: str) -> int:
    """获取模型上下文窗口上限。

    Args:
        model_name: 模型名称。

    Returns:
        int: 上下文窗口上限。

    Raises:
        Exception: 模型信息查询异常未被内部拦截时向上抛出。
    """
    if not model_name:
        return DEFAULT_CONTEXT_LIMIT

    name_lower = model_name.lower().strip()
    try:
        litellm = _get_litellm()
    except Exception:
        return DEFAULT_CONTEXT_LIMIT

    for attempt_name in [model_name, name_lower]:
        try:
            model_info = litellm.get_model_info(attempt_name)
            max_tokens = model_info.get("max_input_tokens", model_info.get("max_tokens", None))
            if max_tokens and max_tokens > 0:
                return max_tokens
        except Exception:
            continue

    return DEFAULT_CONTEXT_LIMIT


def calculate_compression_threshold(context_limit: int) -> int:
    """计算压缩阈值。

    Args:
        context_limit: 上下文窗口上限。

    Returns:
        int: 建议压缩阈值。

    Raises:
        Exception: 阈值计算失败时向上抛出。
    """
    if context_limit > 131073:
        return int(context_limit * 0.80)
    return int(context_limit * 0.85)
