class CheckpointGateway:
    def create_checkpoint(self, task_type, input_params, metadata=None):
        raise NotImplementedError

    def load_checkpoint(self, checkpoint_id):
        raise NotImplementedError

    def update_progress(self, checkpoint_id, **kwargs):
        raise NotImplementedError

    def save_slice_result(self, checkpoint_id, slice_index, content, status="completed"):
        raise NotImplementedError

    def get_slice_result(self, checkpoint_id, slice_index):
        raise NotImplementedError

    def mark_slice_completed(self, checkpoint_id, slice_index):
        raise NotImplementedError

    def save_llm_state(self, checkpoint_id, messages, **kwargs):
        raise NotImplementedError

    def load_llm_state(self, checkpoint_id):
        raise NotImplementedError

    def mark_completed(self, checkpoint_id, final_output_path=None):
        raise NotImplementedError

    def mark_failed(self, checkpoint_id, error_message):
        raise NotImplementedError

    def list_checkpoints(self, task_type=None, status=None):
        raise NotImplementedError

    def delete_checkpoint(self, checkpoint_id):
        raise NotImplementedError

    def get_temp_dir(self, checkpoint_id):
        raise NotImplementedError


class DefaultCheckpointGateway(CheckpointGateway):
    def __init__(self, manager):
        self.manager = manager

    def create_checkpoint(self, task_type, input_params, metadata=None):
        return self.manager.create_checkpoint(task_type=task_type, input_params=input_params, metadata=metadata)

    def load_checkpoint(self, checkpoint_id):
        return self.manager.load_checkpoint(checkpoint_id)

    def update_progress(self, checkpoint_id, **kwargs):
        return self.manager.update_progress(checkpoint_id, **kwargs)

    def save_slice_result(self, checkpoint_id, slice_index, content, status="completed"):
        return self.manager.save_slice_result(checkpoint_id, slice_index, content, status)

    def get_slice_result(self, checkpoint_id, slice_index):
        return self.manager.get_slice_result(checkpoint_id, slice_index)

    def mark_slice_completed(self, checkpoint_id, slice_index):
        return self.manager.mark_slice_completed(checkpoint_id, slice_index)

    def save_llm_state(self, checkpoint_id, messages, **kwargs):
        return self.manager.save_llm_state(checkpoint_id, messages, **kwargs)

    def load_llm_state(self, checkpoint_id):
        return self.manager.load_llm_state(checkpoint_id)

    def mark_completed(self, checkpoint_id, final_output_path=None):
        return self.manager.mark_completed(checkpoint_id, final_output_path=final_output_path)

    def mark_failed(self, checkpoint_id, error_message):
        return self.manager.mark_failed(checkpoint_id, error_message)

    def list_checkpoints(self, task_type=None, status=None):
        return self.manager.list_checkpoints(task_type=task_type, status=status)

    def delete_checkpoint(self, checkpoint_id):
        return self.manager.delete_checkpoint(checkpoint_id)

    def get_temp_dir(self, checkpoint_id):
        return self.manager.get_temp_dir(checkpoint_id)


__all__ = ["CheckpointGateway", "DefaultCheckpointGateway"]
