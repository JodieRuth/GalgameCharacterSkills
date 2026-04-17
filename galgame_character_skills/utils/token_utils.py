import tiktoken

_tokenizer = tiktoken.get_encoding("cl100k_base")


def estimate_tokens_from_text(text):
    if not text:
        return 0
    try:
        return len(_tokenizer.encode(text))
    except Exception:
        return max(1, len(text) // 2)
