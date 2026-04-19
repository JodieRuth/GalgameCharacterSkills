DEFAULT_CONTEXT_LIMIT = 115000
_litellm_module = None


def _get_litellm():
    global _litellm_module
    if _litellm_module is None:
        import litellm

        _litellm_module = litellm
    return _litellm_module


def get_model_context_limit(model_name):
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


def calculate_compression_threshold(context_limit):
    if context_limit > 131073:
        return int(context_limit * 0.80)
    return int(context_limit * 0.85)
