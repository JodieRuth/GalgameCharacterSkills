from galgame_character_skills.api.task_api_service import generate_skills_result


def test_generate_skills_result_requires_role_name():
    result = generate_skills_result({}, lambda x: {"a": 1}, lambda x: {"b": 2})
    assert result["success"] is False
    assert "角色名称" in result["message"]


def test_generate_skills_result_dispatches_to_skills_handler():
    calls = {"skills": 0, "card": 0}

    def skills_handler(data):
        calls["skills"] += 1
        return {"success": True, "target": "skills"}

    def card_handler(data):
        calls["card"] += 1
        return {"success": True, "target": "card"}

    r1 = generate_skills_result({"role_name": "a", "mode": "skills"}, skills_handler, card_handler)

    assert r1["target"] == "skills"
    assert calls == {"skills": 1, "card": 0}


def test_generate_skills_result_dispatches_to_character_card_handler():
    calls = {"skills": 0, "card": 0}

    def skills_handler(data):
        calls["skills"] += 1
        return {"success": True, "target": "skills"}

    def card_handler(data):
        calls["card"] += 1
        return {"success": True, "target": "card"}

    r2 = generate_skills_result({"role_name": "a", "mode": "chara_card"}, skills_handler, card_handler)

    assert r2["target"] == "card"
    assert calls == {"skills": 0, "card": 1}
