from galgame_character_skills.api.config_api_service import get_config_result
from galgame_character_skills.app import create_app
from galgame_character_skills.config import AppSettings


def test_get_config_result_masks_apikey():
    result = get_config_result(
        lambda: AppSettings(
            baseurl="https://example.test/v1",
            modelname="openai/gpt-4o-mini",
            apikey="abcdef123456",
            max_retries=5,
            workspace_dir="workspace",
        )
    )
    assert result == {
        "success": True,
        "baseurl": "https://example.test/v1",
        "modelname": "openai/gpt-4o-mini",
        "max_retries": 5,
        "workspace_dir": "workspace",
        "has_apikey": True,
        "apikey_masked": "abc***56",
    }


def test_get_config_result_handles_empty_apikey():
    result = get_config_result(lambda: AppSettings())
    assert result["success"] is True
    assert result["has_apikey"] is False
    assert result["apikey_masked"] == ""


def test_get_config_route_returns_payload(monkeypatch):
    class DummyDeps:
        file_processor = object()
        r18_traits = set()

    class DummyRuntime:
        checkpoint_gateway = object()
        vndb_gateway = object()

    monkeypatch.setattr(
        "galgame_character_skills.app.get_app_settings",
        lambda: AppSettings(
            baseurl="https://example.test/v1",
            modelname="model-x",
            apikey="123456",
            max_retries=4,
            workspace_dir="workspace",
        ),
    )
    app = create_app(app_dependencies=DummyDeps(), task_runtime=DummyRuntime())
    with app.test_client() as client:
        resp = client.get("/api/config")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["success"] is True
    assert data["baseurl"] == "https://example.test/v1"
    assert data["modelname"] == "model-x"
    assert data["max_retries"] == 4
    assert data["workspace_dir"] == "workspace"
    assert data["has_apikey"] is True
    assert data["apikey_masked"] == "******"
