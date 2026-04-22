from galgame_character_skills.api.validators import require_non_empty_field, require_condition


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


@require_non_empty_field("file_path", "未提供文件路径", data_arg_index=1)
def _tokens_handler(_processor, data):
    return {"success": True, "file_path": data["file_path"]}


def test_require_non_empty_field_supports_data_arg_index():
    failed = _tokens_handler(object(), {})
    assert failed["success"] is False
    assert failed["message"] == "未提供文件路径"

    passed = _tokens_handler(object(), {"file_path": "a.md"})
    assert passed["success"] is True
    assert passed["file_path"] == "a.md"


@require_condition(
    lambda data, _processor, extract_file_paths: bool(extract_file_paths(data)),
    "请先选择文件",
    data_arg_index=1,
)
def _slice_handler(processor, data, extract_file_paths):
    return {"success": True, "count": len(extract_file_paths(data)), "processor": processor}


def test_require_condition_uses_data_and_remaining_args():
    extract = lambda data: data.get("file_paths", [])
    failed = _slice_handler("fp", {}, extract)
    assert failed["success"] is False
    assert failed["message"] == "请先选择文件"

    passed = _slice_handler("fp", {"file_paths": ["a.md", "b.md"]}, extract)
    assert passed["success"] is True
    assert passed["count"] == 2
