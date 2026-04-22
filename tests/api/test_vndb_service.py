from galgame_character_skills.api.vndb_service import fetch_vndb_character


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeGateway:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def query_character(self, char_id, timeout):
        self.calls.append((char_id, timeout))
        if self._error is not None:
            raise self._error
        return self._response


def test_fetch_vndb_character_rejects_empty_id():
    gateway = _FakeGateway()
    result = fetch_vndb_character("", set(), gateway)
    assert result["success"] is False
    assert result["message"] == "未提供VNDB ID"
    assert gateway.calls == []


def test_fetch_vndb_character_rejects_invalid_id_format():
    gateway = _FakeGateway()
    result = fetch_vndb_character("abc", set(), gateway)
    assert result["success"] is False
    assert result["message"] == "无效的VNDB ID格式，应为 c+数字 或纯数字"
    assert gateway.calls == []


def test_fetch_vndb_character_returns_not_found_for_empty_results():
    response = _FakeResponse(200, {"results": []})
    gateway = _FakeGateway(response=response)
    result = fetch_vndb_character("123", set(), gateway)
    assert result["success"] is False
    assert result["message"] == "未找到该角色"
    assert gateway.calls == [("123", 10)]


def test_fetch_vndb_character_returns_http_error():
    response = _FakeResponse(500, {})
    gateway = _FakeGateway(response=response)
    result = fetch_vndb_character("123", set(), gateway)
    assert result["success"] is False
    assert result["message"] == "VNDB API请求失败: HTTP 500"
    assert gateway.calls == [("123", 10)]


def test_fetch_vndb_character_handles_timeout():
    gateway = _FakeGateway(error=TimeoutError())
    result = fetch_vndb_character("123", set(), gateway)
    assert result["success"] is False
    assert result["message"] == "VNDB API请求超时"
    assert gateway.calls == [("123", 10)]


def test_fetch_vndb_character_handles_unknown_exception():
    gateway = _FakeGateway(error=RuntimeError("boom"))
    result = fetch_vndb_character("123", set(), gateway)
    assert result["success"] is False
    assert result["message"] == "获取VNDB信息失败: boom"
    assert gateway.calls == [("123", 10)]


def test_fetch_vndb_character_parses_payload_and_filters_r18_traits():
    payload = {
        "results": [
            {
                "name": "Alice",
                "original": "アリス",
                "aliases": ["A"],
                "description": "desc",
                "age": "18",
                "birthday": [1, 2],
                "blood_type": "A",
                "height": "160",
                "weight": "50",
                "bust": "80",
                "waist": "60",
                "hips": "85",
                "image": {"url": "http://img"},
                "traits": [{"name": "Brave"}, {"name": "R18Tag"}],
                "vns": [{"title": "VN-1"}, {"title": ""}],
            }
        ]
    }
    gateway = _FakeGateway(response=_FakeResponse(200, payload))
    result = fetch_vndb_character("c456", {"R18Tag"}, gateway)

    assert result["success"] is True
    assert gateway.calls == [("456", 10)]
    data = result["data"]
    assert data["vndb_id"] == "c456"
    assert data["name"] == "Alice"
    assert data["birthday"] == "1/2"
    assert data["traits"] == ["Brave"]
    assert data["vns"] == ["VN-1"]
