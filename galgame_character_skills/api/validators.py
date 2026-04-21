from functools import wraps

from ..domain import fail_result


def require_non_empty_field(field_name, message):
    def decorator(func):
        @wraps(func)
        def wrapper(data, *args, **kwargs):
            value = (data or {}).get(field_name)
            if not value:
                return fail_result(message)
            return func(data, *args, **kwargs)

        return wrapper

    return decorator


__all__ = ["require_non_empty_field"]
