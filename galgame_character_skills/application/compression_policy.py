"""压缩策略模块，根据模型上下文与估算 token 决定是否压缩输入。"""

from ..utils.llm_budget import get_model_context_limit, calculate_compression_threshold


def resolve_compression_policy(model_name, raw_estimated_tokens, force_no_compression):
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
