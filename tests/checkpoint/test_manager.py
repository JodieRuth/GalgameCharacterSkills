from galgame_character_skills.checkpoint import manager as manager_module


def test_checkpoint_manager_defaults_to_workspace_checkpoints_dir(monkeypatch):
    monkeypatch.setattr(manager_module, "get_workspace_checkpoints_dir", lambda: "D:/workspace/checkpoints")
    monkeypatch.setattr(manager_module.os, "makedirs", lambda *args, **kwargs: None)

    manager = manager_module.CheckpointManager(use_singleton=False)

    assert manager.checkpoint_dir == "D:/workspace/checkpoints"
    assert manager.temp_dir.replace("\\", "/") == "D:/workspace/checkpoints/temp"


def test_checkpoint_manager_respects_explicit_checkpoint_dir(monkeypatch):
    monkeypatch.setattr(manager_module.os, "makedirs", lambda *args, **kwargs: None)

    manager = manager_module.CheckpointManager(
        checkpoint_dir="D:/custom/checkpoints",
        use_singleton=False,
    )

    assert manager.checkpoint_dir == "D:/custom/checkpoints"
