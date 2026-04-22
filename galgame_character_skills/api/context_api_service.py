"""上下文窗口查询接口模块，提供模型上下文上限查询结果。"""

from typing import Any, Callable

from ..domain import ok_result


def get_context_limit_result(
    data: dict[str, Any],
    get_model_context_limit: Callable[[str], int],
) -> dict[str, Any]:
    """获取模型上下文窗口上限。

    Args:
        data: 请求数据。
        get_model_context_limit: 上下文上限查询函数。

    Returns:
        dict[str, Any]: 上下文上限结果。

    Raises:
        Exception: 上下文查询失败时向上抛出。
    """
    model_name = data.get('model_name', '')
    limit = get_model_context_limit(model_name)
    return ok_result(context_limit=limit)
