def load_resumable_checkpoint(ckpt_manager, checkpoint_id):
    ckpt = ckpt_manager.load_checkpoint(checkpoint_id)
    if not ckpt:
        return None, {'success': False, 'message': f'未找到Checkpoint: {checkpoint_id}'}
    if ckpt['status'] == 'completed':
        return None, {'success': False, 'message': '该任务已完成，无需恢复'}
    return ckpt, None
