"""LLM 传输模块，封装对 LiteLLM completion 接口的重试与调用细节。"""

import time
from typing import Any, Callable

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


class CompletionTransport:
    def complete_with_retry(
        self,
        kwargs: dict[str, Any],
        max_retries: int,
        on_attempt_failed: Callable[[int, Exception, int], None] | None = None,
        on_retry_wait: Callable[[int, int, int], None] | None = None,
        on_success: Callable[[Any], None] | None = None,
        on_final_failure: Callable[[Exception], None] | None = None,
    ) -> Any:
        """执行带重试的 completion 调用。

        Args:
            kwargs: completion 调用参数。
            max_retries: 最大重试次数。
            on_attempt_failed: 单次失败回调。
            on_retry_wait: 重试等待回调。
            on_success: 成功回调。
            on_final_failure: 最终失败回调。

        Returns:
            Any: completion 响应对象，失败时返回 None。

        Raises:
            Exception: 回调执行失败时向上抛出。
        """
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
