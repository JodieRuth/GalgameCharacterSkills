from ..checkpoint import load_resumable_checkpoint


def prepare_request_with_checkpoint(
    request_data,
    checkpoint_gateway,
    task_type,
    load_resume_state,
    build_initial_state,
    load_resumable_checkpoint_fn=load_resumable_checkpoint,
):
    if request_data.resume_checkpoint_id:
        ckpt_result = load_resumable_checkpoint_fn(checkpoint_gateway, request_data.resume_checkpoint_id)
        if not ckpt_result.get("success"):
            return None, ckpt_result

        ckpt = ckpt_result["checkpoint"]
        request_data.apply_checkpoint(ckpt["input_params"])
        checkpoint_id = request_data.resume_checkpoint_id
        state = load_resume_state(checkpoint_gateway, checkpoint_id, ckpt)
        return {
            "checkpoint_id": checkpoint_id,
            "state": state,
            "resumed": True,
            "checkpoint": ckpt,
        }, None

    checkpoint_id = checkpoint_gateway.create_checkpoint(
        task_type=task_type,
        input_params=request_data.to_checkpoint_input(),
    )
    return {
        "checkpoint_id": checkpoint_id,
        "state": build_initial_state(),
        "resumed": False,
        "checkpoint": None,
    }, None


__all__ = ["prepare_request_with_checkpoint"]
