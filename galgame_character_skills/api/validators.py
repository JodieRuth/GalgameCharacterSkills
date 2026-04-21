"""API 参数校验装饰器模块，封装常用的请求字段前置校验逻辑。"""

from functools import wraps

from ..domain import fail_result


def _extract_data_and_remaining_args(args, data_arg_index):
    if data_arg_index < 0 or data_arg_index >= len(args):
        return {}, args
    data = args[data_arg_index] or {}
    remaining = args[:data_arg_index] + args[data_arg_index + 1:]
    return data, remaining


def require_non_empty_field(field_name, message, data_arg_index=0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            data, _ = _extract_data_and_remaining_args(args, data_arg_index)
            value = data.get(field_name)
            if not value:
                return fail_result(message)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_condition(predicate, message, data_arg_index=0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            data, remaining_args = _extract_data_and_remaining_args(args, data_arg_index)
            if not predicate(data, *remaining_args, **kwargs):
                return fail_result(message)
            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = ["require_non_empty_field", "require_condition"]
