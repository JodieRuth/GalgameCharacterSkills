"""压缩策略模块，根据模型上下文与估算 token 决定是否压缩输入。"""

from ..llm.budget import get_model_context_limit, calculate_compression_threshold


def resolve_compression_policy(
    model_name: str,
    raw_estimated_tokens: int,
    force_no_compression: bool,
) -> dict[str, int | bool]:
    """解析压缩策略。

    Args:
        model_name: 模型名称。
        raw_estimated_tokens: 原始 token 估算值。
        force_no_compression: 是否强制不压缩。

    Returns:
        dict[str, int | bool]: 压缩判定结果。

    Raises:
        Exception: 模型上下文读取失败时向上抛出。
    """
    context_limit = get_model_context_limit(model_name)
    context_limit_tokens = calculate_compression_threshold(context_limit)
    should_compress = (not force_no_compression) and raw_estimated_tokens > context_limit_tokens
    return {
        "context_limit": context_limit,
        "context_limit_tokens": context_limit_tokens,
        "should_compress": should_compress,
        "force_exceeds_limit": force_no_compression and raw_estimated_tokens > context_limit_tokens,
    }


__all__ = ["resolve_compression_policy"]
