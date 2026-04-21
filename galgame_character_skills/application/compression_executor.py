"""压缩执行模块，根据运行时依赖驱动 summary 或分析文本压缩流程。"""

def run_compression_pipeline(
    *,
    runtime,
    model_name,
    compression_mode,
    force_no_compression,
    raw_estimated_tokens,
    policy,
    llm_compress,
    fallback_compress,
    log_prefix="",
):
    context_limit = policy["context_limit"]
    context_limit_tokens = policy["context_limit_tokens"]
    target_budget_tokens = context_limit_tokens

    print(f"Model: {model_name}, Context limit: {context_limit}, Threshold: {context_limit_tokens}")
    print(
        f"{log_prefix}Compression mode: {compression_mode}, Force no compression: {force_no_compression}, "
        f"Raw tokens: {raw_estimated_tokens}, Limit: {context_limit_tokens}"
    )

    if policy["should_compress"]:
        if compression_mode == "llm":
            compressed = llm_compress(target_budget_tokens)
        else:
            compressed = fallback_compress(target_budget_tokens)
        return compressed, True, context_limit, context_limit_tokens

    if policy["force_exceeds_limit"]:
        print("Force no compression enabled, using full context despite exceeding limit")
    else:
        print(f"No compression needed ({raw_estimated_tokens} <= {context_limit_tokens})")
    return None, False, context_limit, context_limit_tokens


__all__ = ["run_compression_pipeline"]
