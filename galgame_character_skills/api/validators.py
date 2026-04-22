"""API 参数校验装饰器模块，封装常用的请求字段前置校验逻辑。"""

from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

from ..domain import fail_result

P = ParamSpec("P")
R = TypeVar("R")

def _extract_data_and_remaining_args(
    args: tuple[Any, ...],
    data_arg_index: int,
) -> tuple[dict[str, Any], tuple[Any, ...]]:
    """提取装饰器中的数据参数和剩余参数。

    Args:
        args: 原始位置参数。
        data_arg_index: 数据参数索引。

    Returns:
        tuple[dict[str, Any], tuple[Any, ...]]: 数据参数和剩余参数。

    Raises:
        Exception: 参数提取失败时向上抛出。
    """
    if data_arg_index < 0 or data_arg_index >= len(args):
        return {}, args
    data = args[data_arg_index] or {}
    remaining = args[:data_arg_index] + args[data_arg_index + 1:]
    return data, remaining


def require_non_empty_field(
    field_name: str,
    message: str,
    data_arg_index: int = 0,
) -> Callable[[Callable[P, R]], Callable[P, R | dict[str, Any]]]:
    """校验指定字段非空。

    Args:
        field_name: 需要校验的字段名。
        message: 校验失败消息。
        data_arg_index: 数据参数索引。

    Returns:
        Callable[[Callable[P, R]], Callable[P, R | dict[str, Any]]]: 装饰器函数。

    Raises:
        Exception: 校验流程失败时向上抛出。
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R | dict[str, Any]]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | dict[str, Any]:
            data, _ = _extract_data_and_remaining_args(args, data_arg_index)
            value = data.get(field_name)
            if not value:
                return fail_result(message)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_condition(
    predicate: Callable[..., bool],
    message: str,
    data_arg_index: int = 0,
) -> Callable[[Callable[P, R]], Callable[P, R | dict[str, Any]]]:
    """按自定义条件校验请求。

    Args:
        predicate: 条件判断函数。
        message: 校验失败消息。
        data_arg_index: 数据参数索引。

    Returns:
        Callable[[Callable[P, R]], Callable[P, R | dict[str, Any]]]: 装饰器函数。

    Raises:
        Exception: 校验流程失败时向上抛出。
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R | dict[str, Any]]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | dict[str, Any]:
            data, remaining_args = _extract_data_and_remaining_args(args, data_arg_index)
            if not predicate(data, *remaining_args, **kwargs):
                return fail_result(message)
            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = ["require_non_empty_field", "require_condition"]
