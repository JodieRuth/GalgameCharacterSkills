from unittest.mock import Mock

from galgame_character_skills.gateways.checkpoint_gateway import DefaultCheckpointGateway


def test_create_checkpoint_delegates_with_named_arguments():
    manager = Mock()
    manager.create_checkpoint.return_value = "ckpt-1"
    gateway = DefaultCheckpointGateway(manager)

    result = gateway.create_checkpoint("summary", {"role_name": "A"}, metadata={"source": "test"})

    assert result == "ckpt-1"
    manager.create_checkpoint.assert_called_once_with(
        task_type="summary",
        input_params={"role_name": "A"},
        metadata={"source": "test"},
    )


def test_update_progress_delegates_kwargs():
    manager = Mock()
    manager.update_progress.return_value = True
    gateway = DefaultCheckpointGateway(manager)

    result = gateway.update_progress("ckpt-1", current_slice=2, total_slices=10)

    assert result is True
    manager.update_progress.assert_called_once_with("ckpt-1", current_slice=2, total_slices=10)


def test_save_slice_result_uses_default_status_when_not_provided():
    manager = Mock()
    manager.save_slice_result.return_value = None
    gateway = DefaultCheckpointGateway(manager)

    gateway.save_slice_result("ckpt-1", 3, "content")

    manager.save_slice_result.assert_called_once_with("ckpt-1", 3, "content", "completed")


def test_mark_completed_passes_final_output_path_by_keyword():
    manager = Mock()
    manager.mark_completed.return_value = True
    gateway = DefaultCheckpointGateway(manager)

    result = gateway.mark_completed("ckpt-1", final_output_path="out.json")

    assert result is True
    manager.mark_completed.assert_called_once_with("ckpt-1", final_output_path="out.json")
