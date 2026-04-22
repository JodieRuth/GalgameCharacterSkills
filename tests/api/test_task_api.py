from galgame_character_skills.api.task_api import TaskApi


def test_dispatch_skills_mode_requires_role_name():
    api = TaskApi(runtime=None)

    result = api.dispatch_skills_mode({})

    assert result["success"] is False
    assert "角色名称" in result["message"]


def test_dispatch_skills_mode_dispatches_to_skills_handler():
    calls = {"skills": 0, "card": 0}

    class FakeTaskApi(TaskApi):
        def __init__(self):
            pass

        def generate_skills_folder(self, data):
            calls["skills"] += 1
            return {"success": True, "target": "skills"}

        def generate_character_card(self, data):
            calls["card"] += 1
            return {"success": True, "target": "card"}

    api = FakeTaskApi()
    result = api.dispatch_skills_mode({"role_name": "a", "mode": "skills"})

    assert result["target"] == "skills"
    assert calls == {"skills": 1, "card": 0}


def test_dispatch_skills_mode_dispatches_to_character_card():
    calls = {"skills": 0, "card": 0}

    class FakeTaskApi(TaskApi):
        def __init__(self):
            pass

        def generate_skills_folder(self, data):
            calls["skills"] += 1
            return {"success": True, "target": "skills"}

        def generate_character_card(self, data):
            calls["card"] += 1
            return {"success": True, "target": "card"}

    api = FakeTaskApi()
    result = api.dispatch_skills_mode({"role_name": "a", "mode": "chara_card"})

    assert result["target"] == "card"
    assert calls == {"skills": 0, "card": 1}
