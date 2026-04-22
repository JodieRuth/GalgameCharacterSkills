import galgame_character_skills.config.settings as settings_module


def test_get_app_settings_reads_dotenv_defaults(monkeypatch):
    monkeypatch.setattr(settings_module, "get_base_dir", lambda: "D:/project")
    monkeypatch.setattr(
        settings_module,
        "_parse_dotenv_file",
        lambda _: {
            "GCS_BASEURL": "https://example.test/v1",
            "GCS_MODELNAME": "openai/gpt-4o-mini",
            "GCS_APIKEY": "abc123",
            "GCS_MAX_RETRIES": "4",
            "GCS_WORKSPACE_DIR": "workspace-data",
        },
    )
    settings_module.reset_app_settings_cache()

    settings = settings_module.get_app_settings()
    assert settings.baseurl == "https://example.test/v1"
    assert settings.modelname == "openai/gpt-4o-mini"
    assert settings.apikey == "abc123"
    assert settings.max_retries == 4
    assert settings.workspace_dir == "workspace-data"


def test_get_app_settings_prefers_process_env_over_dotenv(monkeypatch):
    monkeypatch.setattr(settings_module, "get_base_dir", lambda: "D:/project")
    monkeypatch.setattr(
        settings_module,
        "_parse_dotenv_file",
        lambda _: {
            "GCS_BASEURL": "https://dotenv.test/v1",
            "GCS_MODELNAME": "model-dotenv",
            "GCS_APIKEY": "dotenv-key",
            "GCS_MAX_RETRIES": "3",
        },
    )
    monkeypatch.setenv("GCS_BASEURL", "https://env.test/v1")
    monkeypatch.setenv("GCS_MODELNAME", "model-env")
    monkeypatch.setenv("GCS_APIKEY", "env-key")
    monkeypatch.setenv("GCS_MAX_RETRIES", "9")
    settings_module.reset_app_settings_cache()

    settings = settings_module.get_app_settings()
    assert settings.baseurl == "https://env.test/v1"
    assert settings.modelname == "model-env"
    assert settings.apikey == "env-key"
    assert settings.max_retries == 9


def test_get_app_settings_ignores_invalid_retry_values(monkeypatch):
    monkeypatch.setattr(settings_module, "get_base_dir", lambda: "D:/project")
    monkeypatch.setattr(
        settings_module,
        "_parse_dotenv_file",
        lambda _: {"GCS_MAX_RETRIES": "not-a-number"},
    )
    settings_module.reset_app_settings_cache()

    settings = settings_module.get_app_settings()
    assert settings.max_retries is None
