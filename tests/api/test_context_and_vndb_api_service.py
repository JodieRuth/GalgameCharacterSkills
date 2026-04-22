from galgame_character_skills.api.context_api_service import get_context_limit_result
from galgame_character_skills.api.vndb_api_service import get_vndb_info_result


def test_get_context_limit_result():
    result = get_context_limit_result({"model_name": "gpt-x"}, lambda m: 123456 if m == "gpt-x" else 0)
    assert result == {"success": True, "context_limit": 123456}


def test_get_vndb_info_result_passthrough():
    called = {}

    def fetch_vndb_character(vndb_id, r18_traits, gateway):
        called["args"] = (vndb_id, r18_traits, gateway)
        return {"success": True, "data": {"vndb_id": vndb_id}}

    result = get_vndb_info_result({"vndb_id": "c123"}, {"x"}, object(), fetch_vndb_character)
    assert result["success"] is True
    assert called["args"][0] == "c123"


def test_get_vndb_info_result_requires_vndb_id():
    called = {"count": 0}

    def fetch_vndb_character(vndb_id, r18_traits, gateway):
        called["count"] += 1
        return {"success": True, "data": {"vndb_id": vndb_id}}

    result = get_vndb_info_result({}, {"x"}, object(), fetch_vndb_character)
    assert result["success"] is False
    assert result["message"] == "未提供VNDB ID"
    assert called["count"] == 0
