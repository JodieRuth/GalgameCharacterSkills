from galgame_character_skills.config.settings import AppSettings
from galgame_character_skills.workspace import paths as paths_module


def test_get_workspace_root_uses_base_dir_when_workspace_is_empty(monkeypatch):
    monkeypatch.setattr(paths_module, "get_base_dir", lambda: "D:/project")
    monkeypatch.setattr(paths_module, "get_app_settings", lambda: AppSettings(workspace_dir=""))

    assert paths_module.get_workspace_root() == "D:\\project"


def test_get_workspace_root_resolves_relative_workspace_dir(monkeypatch):
    monkeypatch.setattr(paths_module, "get_base_dir", lambda: "D:/project")
    monkeypatch.setattr(paths_module, "get_app_settings", lambda: AppSettings(workspace_dir="workspace-data"))

    assert paths_module.get_workspace_root() == "D:\\project\\workspace-data"


def test_get_workspace_root_preserves_absolute_workspace_dir(monkeypatch):
    monkeypatch.setattr(paths_module, "get_base_dir", lambda: "D:/project")
    monkeypatch.setattr(paths_module, "get_app_settings", lambda: AppSettings(workspace_dir="E:/gcs-workspace"))

    assert paths_module.get_workspace_root() == "E:\\gcs-workspace"


def test_workspace_subdirs_are_built_from_workspace_root(monkeypatch):
    monkeypatch.setattr(paths_module, "get_workspace_root", lambda: "D:\\workspace")

    assert paths_module.get_workspace_uploads_dir() == "D:\\workspace\\uploads"
    assert paths_module.get_workspace_summaries_dir() == "D:\\workspace\\summaries"
    assert paths_module.get_workspace_skills_dir() == "D:\\workspace\\skills"
    assert paths_module.get_workspace_cards_dir() == "D:\\workspace\\cards"
    assert paths_module.get_workspace_checkpoints_dir() == "D:\\workspace\\checkpoints"
