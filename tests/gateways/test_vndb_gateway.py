import pytest
import requests

from galgame_character_skills.gateways.vndb_gateway import DefaultVndbGateway


class _FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


def test_query_character_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse(status_code=200)

    monkeypatch.setattr(
        "galgame_character_skills.gateways.vndb_gateway.requests.post",
        fake_post,
    )

    gateway = DefaultVndbGateway(endpoint="https://example.test/character")
    response = gateway.query_character("123", timeout=8)

    assert response.status_code == 200
    assert captured["url"] == "https://example.test/character"
    assert captured["timeout"] == 8
    assert captured["json"]["filters"] == ["id", "=", "c123"]
    assert "traits.name" in captured["json"]["fields"]


def test_query_character_converts_requests_timeout_to_builtin_timeout(monkeypatch):
    def fake_post(url, json, timeout):
        raise requests.exceptions.Timeout("timeout")

    monkeypatch.setattr(
        "galgame_character_skills.gateways.vndb_gateway.requests.post",
        fake_post,
    )

    gateway = DefaultVndbGateway()
    with pytest.raises(TimeoutError, match="VNDB API timeout"):
        gateway.query_character("456", timeout=3)
