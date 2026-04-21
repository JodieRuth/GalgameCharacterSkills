from galgame_character_skills.api.validators import require_non_empty_field


@require_non_empty_field("role_name", "请输入角色名称")
def handle_role_payload(data, marker):
    return {"success": True, "marker": marker, "role_name": data["role_name"]}


def test_require_non_empty_field_requires_role_name():
    result = handle_role_payload({}, "x")
    assert result["success"] is False
    assert result["message"] == "请输入角色名称"


def test_require_non_empty_field_passes_when_role_name_present():
    result = handle_role_payload({"role_name": "rin"}, "ok")
    assert result["success"] is True
    assert result["marker"] == "ok"
    assert result["role_name"] == "rin"
