"""任务结果工厂模块，统一构造成功/失败结果与 dataclass 映射器。"""

from dataclasses import MISSING, fields

from ..domain import ok_result, fail_result


def ok_task_result(message=None, checkpoint_id=None, can_resume=None, **payload):
    extra = dict(payload)
    if checkpoint_id is not None:
        extra["checkpoint_id"] = checkpoint_id
    if can_resume is not None:
        extra["can_resume"] = can_resume
    return ok_result(message=message, **extra)


def fail_task_result(message, checkpoint_id=None, can_resume=None, **payload):
    extra = dict(payload)
    if checkpoint_id is not None:
        extra["checkpoint_id"] = checkpoint_id
    if can_resume is not None:
        extra["can_resume"] = can_resume
    return fail_result(message, **extra)


def build_dataclass_result_mapper(result_cls, field_transformers=None):
    transformers = field_transformers or {}

    def mapper(raw_result):
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
