from galgame_character_skills.domain.service_result import ServiceResult, ok_result, fail_result


def test_service_result_to_dict_with_message_and_payload():
    result = ServiceResult(success=True, message="ok", payload={"a": 1}).to_dict()
    assert result == {"success": True, "message": "ok", "a": 1}


def test_ok_result_without_message():
    result = ok_result(data=[1, 2])
    assert result == {"success": True, "data": [1, 2]}


def test_fail_result_with_payload():
    result = fail_result("bad", code=400)
    assert result == {"success": False, "message": "bad", "code": 400}


def test_service_result_to_dict_omits_none_message():
    result = ServiceResult(success=True, message=None, payload={"value": 1}).to_dict()
    assert result == {"success": True, "value": 1}
