from galgame_character_skills.config import AppSettings
from galgame_character_skills.config.request_config import build_llm_config
import galgame_character_skills.config.request_config as request_config


def test_build_llm_config_maps_fields_and_keeps_defaults(monkeypatch):
    monkeypatch.setattr(
        request_config,
        "get_app_settings",
        lambda: AppSettings(),
    )
    data = {"baseurl": "http://x", "modelname": "m1", "apikey": "k"}
    result = build_llm_config(data)
    assert result == {
        "baseurl": "http://x",
        "modelname": "m1",
        "apikey": "k",
        "max_retries": None,
    }


def test_build_llm_config_converts_zero_like_max_retries_to_none(monkeypatch):
    monkeypatch.setattr(
        request_config,
        "get_app_settings",
        lambda: AppSettings(),
    )
    assert build_llm_config({"max_retries": 0})["max_retries"] is None
    assert build_llm_config({"max_retries": ""})["max_retries"] is None


def test_build_llm_config_keeps_positive_max_retries(monkeypatch):
    monkeypatch.setattr(
        request_config,
        "get_app_settings",
        lambda: AppSettings(),
    )
    assert build_llm_config({"max_retries": 3})["max_retries"] == 3


def test_build_llm_config_uses_settings_defaults_when_payload_missing(monkeypatch):
    monkeypatch.setattr(
        request_config,
        "get_app_settings",
        lambda: AppSettings(
            baseurl="http://default",
            modelname="default-model",
            apikey="default-key",
            max_retries=7,
        ),
    )
    result = build_llm_config({})
    assert result == {
        "baseurl": "http://default",
        "modelname": "default-model",
        "apikey": "default-key",
        "max_retries": 7,
    }


def test_build_llm_config_uses_settings_defaults_when_payload_values_are_blank(monkeypatch):
    monkeypatch.setattr(
        request_config,
        "get_app_settings",
        lambda: AppSettings(
            baseurl="http://default",
            modelname="default-model",
            apikey="default-key",
            max_retries=5,
        ),
    )
    result = build_llm_config(
        {"baseurl": "", "modelname": " ", "apikey": "", "max_retries": ""}
    )
    assert result == {
        "baseurl": "http://default",
        "modelname": "default-model",
        "apikey": "default-key",
        "max_retries": 5,
    }
