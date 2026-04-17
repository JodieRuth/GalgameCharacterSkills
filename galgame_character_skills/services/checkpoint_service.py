from ..utils.checkpoint_utils import load_resumable_checkpoint


def list_checkpoints_result(ckpt_manager, task_type=None, status=None):
    checkpoints = ckpt_manager.list_checkpoints(task_type=task_type, status=status)
    return {'success': True, 'checkpoints': checkpoints}


def get_checkpoint_result(ckpt_manager, checkpoint_id):
    ckpt = ckpt_manager.load_checkpoint(checkpoint_id)
    if not ckpt:
        return {'success': False, 'message': f'未找到Checkpoint: {checkpoint_id}'}
    llm_state = ckpt_manager.load_llm_state(checkpoint_id)
    return {'success': True, 'checkpoint': ckpt, 'llm_state': llm_state}


def delete_checkpoint_result(ckpt_manager, checkpoint_id):
    success = ckpt_manager.delete_checkpoint(checkpoint_id)
    if success:
        return {'success': True, 'message': 'Checkpoint已删除'}
    return {'success': False, 'message': f'未找到Checkpoint: {checkpoint_id}'}


def resume_checkpoint_result(
    ckpt_manager,
    checkpoint_id,
    extra_params,
    summarize_handler,
    generate_skills_handler,
    generate_chara_card_handler
):
    ckpt, error = load_resumable_checkpoint(ckpt_manager, checkpoint_id)
    if error:
        return error

    task_type = ckpt['task_type']
    input_params = dict(ckpt.get('input_params', {}))
    input_params['resume_checkpoint_id'] = checkpoint_id
    input_params.update(extra_params or {})

    if task_type == 'summarize':
        return summarize_handler(input_params)
    if task_type == 'generate_skills':
        return generate_skills_handler(input_params)
    if task_type == 'generate_chara_card':
        return generate_chara_card_handler(input_params)
    return {'success': False, 'message': f'未知的任务类型: {task_type}'}
