"""任务准备上下文模块，提供请求清洗、恢复回调与 prepared builder 组合器。"""

from typing import Any, Callable, TypeVar

from ..app_container import TaskRuntimeDependencies
from .checkpoint_prepare import prepare_request_with_checkpoint
from .runtime_logging import log_message

RequestT = TypeVar("RequestT")
PreparedT = TypeVar("PreparedT")


def chain_on_resumed(
    *handlers: Callable[[Any, Any, TaskRuntimeDependencies], None] | None,
) -> Callable[[Any, Any, TaskRuntimeDependencies], None]:
    """串联恢复后的回调函数。

    Args:
        *handlers: 恢复回调函数列表。

    Returns:
        Callable[[Any, Any, TaskRuntimeDependencies], None]: 串联后的回调。

    Raises:
        Exception: 任一回调执行失败时向上抛出。
    """
    def chained(request_data: Any, checkpoint_data: Any, runtime: TaskRuntimeDependencies) -> None:
        for handler in handlers:
            if handler is not None:
                handler(request_data, checkpoint_data, runtime)

    return chained


def build_on_resumed_logger(
    message_builder: Callable[[Any, Any, TaskRuntimeDependencies], str],
) -> Callable[[Any, Any, TaskRuntimeDependencies], None]:
    """构造恢复日志回调。

    Args:
        message_builder: 日志消息构造函数。

    Returns:
        Callable[[Any, Any, TaskRuntimeDependencies], None]: 日志回调。

    Raises:
        Exception: 日志消息构造失败时向上抛出。
    """
    def logger(request_data: Any, checkpoint_data: Any, runtime: TaskRuntimeDependencies) -> None:
        log_message(message_builder(request_data, checkpoint_data, runtime), runtime=runtime)

    return logger


def build_clean_payload_loader(
    request_cls: type[RequestT],
) -> Callable[[dict[str, Any], TaskRuntimeDependencies], RequestT]:
    """构造请求载荷清洗函数。

    Args:
        request_cls: 请求模型类型。

    Returns:
        Callable[[dict[str, Any], TaskRuntimeDependencies], RequestT]: 请求加载函数。

    Raises:
        Exception: 请求模型构造失败时向上抛出。
    """
    def loader(data: dict[str, Any], runtime: TaskRuntimeDependencies) -> RequestT:
        return request_cls.from_payload(data, runtime.clean_vndb_data)

    return loader


def build_basic_prepared_builder(
    prepared_cls: type[PreparedT],
) -> Callable[[RequestT, dict[str, Any], Any], PreparedT]:
    """构造基础 prepared 对象生成函数。

    Args:
        prepared_cls: prepared 类型。

    Returns:
        Callable[[RequestT, dict[str, Any], Any], PreparedT]: prepared 构造函数。

    Raises:
        Exception: prepared 实例化失败时向上抛出。
    """
    def builder(request_data: RequestT, config: dict[str, Any], checkpoint_data: Any) -> PreparedT:
        return prepared_cls(
            request_data=request_data,
            config=config,
            checkpoint_id=checkpoint_data.checkpoint_id,
        )

    return builder


def build_prepared_state_builder(
    prepared_cls: type[PreparedT],
    state_fields: tuple[str, ...],
) -> Callable[[RequestT, dict[str, Any], Any], PreparedT]:
    """构造带恢复状态的 prepared 对象生成函数。

    Args:
        prepared_cls: prepared 类型。
        state_fields: 需要注入的状态字段名。

    Returns:
        Callable[[RequestT, dict[str, Any], Any], PreparedT]: prepared 构造函数。

    Raises:
        Exception: 状态注入或 prepared 实例化失败时向上抛出。
    """
    def builder(request_data: RequestT, config: dict[str, Any], checkpoint_data: Any) -> PreparedT:
        state = checkpoint_data.state
        kwargs = {
            "request_data": request_data,
            "config": config,
            "checkpoint_id": checkpoint_data.checkpoint_id,
        }
        for field_name in state_fields:
            kwargs[field_name] = getattr(state, field_name)
        return prepared_cls(**kwargs)

    return builder


def prepare_task_context(
    data: dict[str, Any],
    runtime: TaskRuntimeDependencies,
    *,
    from_payload: Callable[[dict[str, Any], TaskRuntimeDependencies], RequestT],
    config_builder: Callable[[dict[str, Any]], dict[str, Any]],
    checkpoint_task_type: str,
    load_resume_state: Callable[..., Any],
    build_initial_state: Callable[[], Any],
    load_resumable_checkpoint_fn: Callable[..., dict[str, Any]],
    build_prepared: Callable[[RequestT, dict[str, Any], Any], PreparedT],
    validate_before_checkpoint: Callable[[RequestT, dict[str, Any], TaskRuntimeDependencies], dict[str, Any] | None] | None = None,
    validate_after_checkpoint: Callable[[RequestT, dict[str, Any], TaskRuntimeDependencies, Any], dict[str, Any] | None] | None = None,
    on_resumed: Callable[[RequestT, Any, TaskRuntimeDependencies], None] | None = None,
) -> tuple[PreparedT | None, dict[str, Any] | None]:
    """准备任务执行上下文。

    Args:
        data: 原始请求数据。
        runtime: 任务运行时依赖。
        from_payload: 请求载荷清洗函数。
        config_builder: 配置构造函数。
        checkpoint_task_type: checkpoint 任务类型。
        load_resume_state: 恢复状态加载函数。
        build_initial_state: 初始状态构造函数。
        load_resumable_checkpoint_fn: 可恢复 checkpoint 加载函数。
        build_prepared: prepared 对象构造函数。
        validate_before_checkpoint: checkpoint 前校验函数。
        validate_after_checkpoint: checkpoint 后校验函数。
        on_resumed: 恢复后的回调函数。

    Returns:
        tuple[PreparedT | None, dict[str, Any] | None]: prepared 对象和错误结果。

    Raises:
        Exception: 预处理流程执行失败时向上抛出。
    """
    request_data = from_payload(data, runtime)

    if validate_before_checkpoint:
        error = validate_before_checkpoint(request_data, data, runtime)
        if error:
            return None, error

    config = config_builder(data)

    checkpoint_data, error = prepare_request_with_checkpoint(
        request_data=request_data,
        checkpoint_gateway=runtime.checkpoint_gateway,
        task_type=checkpoint_task_type,
        load_resume_state=load_resume_state,
        build_initial_state=build_initial_state,
        load_resumable_checkpoint_fn=load_resumable_checkpoint_fn,
    )
    if error:
        return None, error

    if checkpoint_data.resumed and on_resumed:
        on_resumed(request_data, checkpoint_data, runtime)

    if validate_after_checkpoint:
        error = validate_after_checkpoint(request_data, data, runtime, checkpoint_data)
        if error:
            return None, error

    return build_prepared(request_data, config, checkpoint_data), None


__all__ = [
    "chain_on_resumed",
    "build_on_resumed_logger",
    "build_clean_payload_loader",
    "build_basic_prepared_builder",
    "build_prepared_state_builder",
    "prepare_task_context",
]
