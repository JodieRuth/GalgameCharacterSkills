"""任务准备上下文模块，提供请求清洗、恢复回调与 prepared builder 组合器。"""

from .checkpoint_prepare import prepare_request_with_checkpoint


def chain_on_resumed(*handlers):
    def chained(request_data, checkpoint_data, runtime):
        for handler in handlers:
            if handler is not None:
                handler(request_data, checkpoint_data, runtime)

    return chained


def build_on_resumed_logger(message_builder):
    def logger(request_data, checkpoint_data, runtime):
        print(message_builder(request_data, checkpoint_data, runtime))

    return logger


def build_clean_payload_loader(request_cls):
    def loader(data, runtime):
        return request_cls.from_payload(data, runtime.clean_vndb_data)

    return loader


def build_basic_prepared_builder(prepared_cls):
    def builder(request_data, config, checkpoint_data):
        return prepared_cls(
            request_data=request_data,
            config=config,
            checkpoint_id=checkpoint_data.checkpoint_id,
        )

    return builder


def build_prepared_state_builder(prepared_cls, state_fields):
    def builder(request_data, config, checkpoint_data):
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
    data,
    runtime,
    *,
    from_payload,
    config_builder,
    checkpoint_task_type,
    load_resume_state,
    build_initial_state,
    load_resumable_checkpoint_fn,
    build_prepared,
    validate_before_checkpoint=None,
    validate_after_checkpoint=None,
    on_resumed=None,
):
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
