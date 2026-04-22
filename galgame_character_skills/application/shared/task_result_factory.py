"""任务结果工厂模块，统一构造成功/失败结果与 dataclass 映射器。"""

from dataclasses import MISSING, fields
from typing import Any, Callable, TypeVar

from ...domain import ok_result, fail_result

ResultT = TypeVar("ResultT")

def ok_task_result(
    message: str | None = None,
    checkpoint_id: str | None = None,
    can_resume: bool | None = None,
    **payload: Any,
) -> dict[str, Any]:
    """构造成功任务结果。

    Args:
        message: 结果消息。
        checkpoint_id: checkpoint 标识。
        can_resume: 是否可恢复。
        **payload: 额外返回字段。

    Returns:
        dict[str, Any]: 统一成功结果。

    Raises:
        Exception: 结果组装失败时向上抛出。
    """
    extra = dict(payload)
    if checkpoint_id is not None:
        extra["checkpoint_id"] = checkpoint_id
    if can_resume is not None:
        extra["can_resume"] = can_resume
    return ok_result(message=message, **extra)


def fail_task_result(
    message: str,
    checkpoint_id: str | None = None,
    can_resume: bool | None = None,
    **payload: Any,
) -> dict[str, Any]:
    """构造失败任务结果。

    Args:
        message: 错误消息。
        checkpoint_id: checkpoint 标识。
        can_resume: 是否可恢复。
        **payload: 额外返回字段。

    Returns:
        dict[str, Any]: 统一失败结果。

    Raises:
        Exception: 结果组装失败时向上抛出。
    """
    extra = dict(payload)
    if checkpoint_id is not None:
        extra["checkpoint_id"] = checkpoint_id
    if can_resume is not None:
        extra["can_resume"] = can_resume
    return fail_result(message, **extra)


def build_dataclass_result_mapper(
    result_cls: type[ResultT],
    field_transformers: dict[str, Callable[[Any], Any]] | None = None,
) -> Callable[[dict[str, Any] | None], ResultT]:
    """构造原始结果到 dataclass 的映射函数。

    Args:
        result_cls: 目标 dataclass 类型。
        field_transformers: 字段值转换器。

    Returns:
        Callable[[dict[str, Any] | None], ResultT]: 结果映射函数。

    Raises:
        Exception: 字段转换或实例化失败时向上抛出。
    """
    transformers = field_transformers or {}

    def mapper(raw_result: dict[str, Any] | None) -> ResultT:
        raw = raw_result or {}
        kwargs = {}
        for f in fields(result_cls):
            if f.name in raw:
                value = raw[f.name]
            elif f.default is not MISSING:
                value = f.default
            elif f.default_factory is not MISSING:  # type: ignore[attr-defined]
                value = f.default_factory()  # type: ignore[misc]
            else:
                value = None

            transform = transformers.get(f.name)
            if transform is not None:
                value = transform(value)
            kwargs[f.name] = value
        return result_cls(**kwargs)

    return mapper


__all__ = ["ok_task_result", "fail_task_result", "build_dataclass_result_mapper"]
