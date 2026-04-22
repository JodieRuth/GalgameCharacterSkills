from galgame_character_skills.application import app_container


def test_build_app_dependencies_wires_components(monkeypatch):
    called = {}

    class FakeFileProcessor:
        pass

    class FakeCheckpointManager:
        def __init__(self, checkpoint_dir=None, use_singleton=True):
            called["checkpoint_manager"] = (checkpoint_dir, use_singleton)

    def fake_configure_werkzeug_logging():
        called["configured"] = True

    def fake_get_base_dir():
        return "/base"

    def fake_load_r18_traits(base_dir):
        called["r18_base_dir"] = base_dir
        return {"r18"}

    monkeypatch.setattr(app_container, "FileProcessor", FakeFileProcessor)
    monkeypatch.setattr(app_container, "CheckpointManager", FakeCheckpointManager)
    monkeypatch.setattr(app_container, "configure_werkzeug_logging", fake_configure_werkzeug_logging)
    monkeypatch.setattr(app_container, "get_base_dir", fake_get_base_dir)
    monkeypatch.setattr(app_container, "load_r18_traits", fake_load_r18_traits)

    deps = app_container.build_app_dependencies(checkpoint_dir="/tmp/ckpt", checkpoint_use_singleton=False)

    assert called["configured"] is True
    assert called["checkpoint_manager"] == ("/tmp/ckpt", False)
    assert called["r18_base_dir"] == "/base"
    assert deps.r18_traits == {"r18"}
    assert isinstance(deps.file_processor, FakeFileProcessor)


def test_build_task_runtime_wires_default_gateways():
    deps = app_container.AppDependencies(
        file_processor=object(),
        ckpt_manager=object(),
        r18_traits=set(),
    )

    runtime = app_container.build_task_runtime(deps)

    assert runtime.file_processor is deps.file_processor
    assert runtime.checkpoint_gateway.manager is deps.ckpt_manager
    assert runtime.clean_vndb_data is app_container.clean_vndb_data
    assert runtime.get_base_dir is app_container.get_base_dir
    assert runtime.get_workspace_summaries_dir is app_container.get_workspace_summaries_dir
    assert runtime.get_workspace_skills_dir is app_container.get_workspace_skills_dir
    assert runtime.get_workspace_cards_dir is app_container.get_workspace_cards_dir
    assert runtime.get_workspace_checkpoints_dir is app_container.get_workspace_checkpoints_dir
    assert runtime.estimate_tokens is app_container.estimate_tokens_from_text
    assert runtime.download_vndb_image is app_container.download_vndb_image
    assert runtime.embed_json_in_png is app_container.embed_json_in_png
