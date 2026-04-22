"""压缩执行模块，根据运行时依赖驱动 summary 或分析文本压缩流程。"""

from typing import Any, Callable

from .app_container import TaskRuntimeDependencies
from .shared.runtime_logging import log_message


def run_compression_pipeline(
    *,
    runtime: TaskRuntimeDependencies,
    model_name: str,
    compression_mode: str,
    force_no_compression: bool,
    raw_estimated_tokens: int,
    policy: dict[str, Any],
    llm_compress: Callable[[int], Any],
    fallback_compress: Callable[[int], Any],
    log_prefix: str = "",
) -> tuple[Any, bool, int, int]:
    """执行压缩策略。

    Args:
        runtime: 任务运行时依赖。
        model_name: 模型名称。
        compression_mode: 压缩模式。
        force_no_compression: 是否强制不压缩。
        raw_estimated_tokens: 原始 token 估算值。
        policy: 压缩策略结果。
        llm_compress: LLM 压缩函数。
        fallback_compress: 兜底压缩函数。
        log_prefix: 日志前缀。

    Returns:
        tuple[Any, bool, int, int]: 压缩结果、是否压缩、上下文上限和阈值。

    Raises:
        Exception: 压缩执行失败时向上抛出。
    """
    context_limit = policy["context_limit"]
    context_limit_tokens = policy["context_limit_tokens"]
    target_budget_tokens = context_limit_tokens

    log_message(f"Model: {model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}", runtime=runtime)
    log_message(
        f"{log_prefix}Compression mode: {compression_mode}, Force no compression: {force_no_compression}, "
        f"Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}",
        runtime=runtime,
    )

    if policy["should_compress"]:
        if compression_mode == "llm":
            compressed = llm_compress(target_budget_tokens)
        else:
            compressed = fallback_compress(target_budget_tokens)
        return compressed, True, context_limit, context_limit_tokens

    if policy["force_exceeds_limit"]:
        log_message("Force no compression enabled, using full context despite exceeding limit", runtime=runtime)
    else:
        log_message(f"No compression needed ({raw_estimated_tokens} <= {context_limit_tokens})", runtime=runtime)
    return None, False, context_limit, context_limit_tokens


__all__ = ["run_compression_pipeline"]
