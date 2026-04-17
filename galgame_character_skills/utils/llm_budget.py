import litellm


def get_model_context_limit(model_name):
    if not model_name:
        return 115000

    name_lower = model_name.lower().strip()

    for attempt_name in [model_name, name_lower]:
        try:
            model_info = litellm.get_model_info(attempt_name)
            max_tokens = model_info.get("max_input_tokens", model_info.get("max_tokens", None))
            if max_tokens and max_tokens > 0:
                return max_tokens
        except Exception:
            continue

    return 115000


def calculate_compression_threshold(context_limit):
    if context_limit > 131073:
        return int(context_limit * 0.80)
    return int(context_limit * 0.85)
