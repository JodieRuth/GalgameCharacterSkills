"""应用层运行时日志辅助函数。"""

from typing import Any, Callable


def get_logger(runtime: Any = None, logger: Callable[[str], None] | None = None) -> Callable[[str], None]:
    """解析日志函数，优先使用显式 logger，其次使用 runtime.log。"""
    if logger is not None:
        return logger
    runtime_logger = getattr(runtime, "log", None)
    if callable(runtime_logger):
        return runtime_logger
    return print


def log_message(message: str, runtime: Any = None, logger: Callable[[str], None] | None = None) -> None:
    """输出应用层日志消息。"""
    get_logger(runtime=runtime, logger=logger)(message)


__all__ = ["get_logger", "log_message"]
