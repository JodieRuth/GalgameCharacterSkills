import time

_litellm_module = None


def _get_litellm():
    global _litellm_module
    if _litellm_module is None:
        import litellm

        _litellm_module = litellm
    return _litellm_module


class CompletionTransport:
    def complete_with_retry(
        self,
        kwargs,
        max_retries,
        on_attempt_failed=None,
        on_retry_wait=None,
        on_success=None,
        on_final_failure=None,
    ):
        retries = max(1, max_retries or 1)
        litellm = _get_litellm()
        for attempt in range(retries):
            try:
                response = litellm.completion(**kwargs)
                if on_success:
                    on_success(response)
                return response
            except Exception as e:
                if on_attempt_failed:
                    on_attempt_failed(attempt, e, retries)
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    if on_retry_wait:
                        on_retry_wait(wait_time, attempt, retries)
                    time.sleep(wait_time)
                else:
                    if on_final_failure:
                        on_final_failure(e)
                    return None


__all__ = ["CompletionTransport"]
