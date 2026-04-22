from galgame_character_skills.api.summary_api_service import (
    scan_summary_roles_result,
    get_summary_files_result,
)


def test_scan_summary_roles_result_sets_success_flag():
    get_base_dir = lambda: "D:/x"
    discover = lambda script_dir: {"roles": ["r1"], "base": script_dir}
    result = scan_summary_roles_result(get_base_dir, discover)
    assert result["success"] is True
    assert result["roles"] == ["r1"]
    assert result["base"] == "D:/x"


def test_get_summary_files_result_requires_role_name():
    get_base_dir = lambda: "/tmp"
    finder = lambda base, role_name, mode="skills": [f"{base}/{role_name}/{mode}.md"]

    invalid = get_summary_files_result({}, get_base_dir, finder)
    assert invalid["success"] is False


def test_get_summary_files_result_success():
    get_base_dir = lambda: "/tmp"
    finder = lambda base, role_name, mode="skills": [f"{base}/{role_name}/{mode}.md"]

    ok = get_summary_files_result({"role_name": "rin", "mode": "skills"}, get_base_dir, finder)
    assert ok["success"] is True
    assert len(ok["files"]) == 1
