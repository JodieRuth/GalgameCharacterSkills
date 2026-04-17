import importlib.util
import sys
import types
import uuid
from datetime import datetime
from pathlib import Path


def _load_task_flows_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "galgame_character_skills" / "llm" / "task_flows.py"
    prompt_builders_path = root / "galgame_character_skills" / "utils" / "prompt_builders.py"

    pkg = sys.modules.get("galgame_character_skills")
    if pkg is None:
        pkg = types.ModuleType("galgame_character_skills")
        pkg.__path__ = [str(root / "galgame_character_skills")]
        sys.modules["galgame_character_skills"] = pkg

    llm_pkg = sys.modules.get("galgame_character_skills.llm")
    if llm_pkg is None:
        llm_pkg = types.ModuleType("galgame_character_skills.llm")
        llm_pkg.__path__ = [str(root / "galgame_character_skills" / "llm")]
        sys.modules["galgame_character_skills.llm"] = llm_pkg

    utils_pkg = sys.modules.get("galgame_character_skills.utils")
    if utils_pkg is None:
        utils_pkg = types.ModuleType("galgame_character_skills.utils")
        utils_pkg.__path__ = [str(root / "galgame_character_skills" / "utils")]
        sys.modules["galgame_character_skills.utils"] = utils_pkg

    pb_mod_name = f"galgame_character_skills.utils.prompt_builders_test_{uuid.uuid4().hex}"
    pb_spec = importlib.util.spec_from_file_location(pb_mod_name, prompt_builders_path)
    pb_module = importlib.util.module_from_spec(pb_spec)
    pb_spec.loader.exec_module(pb_module)
    sys.modules["galgame_character_skills.utils.prompt_builders"] = pb_module

    mod_name = f"galgame_character_skills.llm.task_flows_test_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(mod_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_write_field_tools_schema():
    task_flows = _load_task_flows_module()
    tools = task_flows.build_write_field_tools()
    assert len(tools) == 1
    function_def = tools[0]["function"]
    assert function_def["name"] == "write_field"
    enum_values = function_def["parameters"]["properties"]["field_name"]["enum"]
    assert "description" in enum_values
    assert "depth_prompt" in enum_values


def test_build_initial_character_card_fields_with_vndb_data():
    task_flows = _load_task_flows_module()
    fields = task_flows.build_initial_character_card_fields(
        role_name="Alice",
        creator="",
        vndb_data={"name": "Alice VNDB", "vndb_id": "c123"},
        lorebook_entries=[{"id": 1}],
    )
    assert fields["name"] == "Alice VNDB"
    assert fields["creator"] == "AI Character Generator"
    assert fields["creatorcomment"] == "Character card for Alice VNDB (VNDB: c123)"
    assert fields["tags"] == ["character", "alice_vndb"]
    assert fields["character_book_entries"] == [{"id": 1}]
    datetime.fromisoformat(fields["create_date"])


def test_apply_checkpoint_fields_updates_non_lorebook_only():
    task_flows = _load_task_flows_module()
    fields = {
        "name": "Alice",
        "description": "",
        "character_book_entries": [{"id": 1}],
    }
    ckpt = {
        "name": "Alice2",
        "description": "desc",
        "character_book_entries": [{"id": 9}],
    }
    task_flows.apply_checkpoint_fields(fields, ckpt)
    assert fields["name"] == "Alice2"
    assert fields["description"] == "desc"
    assert fields["character_book_entries"] == [{"id": 1}]


def test_build_character_card_messages_resuming_and_non_resuming(monkeypatch):
    task_flows = _load_task_flows_module()

    messages, iteration = task_flows.build_character_card_messages(
        is_resuming=True,
        ckpt_messages=[{"role": "assistant", "content": "x"}],
        ckpt_iteration_count=4,
        system_prompt="sys",
        role_name="Alice",
    )
    assert messages == [{"role": "assistant", "content": "x"}]
    assert iteration == 4

    monkeypatch.setattr(task_flows, "build_character_card_user_prompt", lambda role: f"user:{role}")
    messages, iteration = task_flows.build_character_card_messages(
        is_resuming=False,
        ckpt_messages=[],
        ckpt_iteration_count=None,
        system_prompt="sys2",
        role_name="Bob",
    )
    assert messages[0] == {"role": "system", "content": "sys2"}
    assert messages[1] == {"role": "user", "content": "user:Bob"}
    assert iteration == 0


def test_build_template_path_and_field_mappings_and_success_result():
    task_flows = _load_task_flows_module()
    path = task_flows.build_character_card_template_path()
    assert path.endswith("utils\\chara_card_template.json") or path.endswith("utils/chara_card_template.json")

    fields = {
        "name": "Alice",
        "description": "d",
        "personality": "",
        "first_mes": "f",
        "mes_example": "",
        "scenario": "s",
        "create_date": "2026-01-01T00:00:00",
        "creatorcomment": "c",
        "system_prompt": "sp",
        "post_history_instructions": "",
        "tags": ["character"],
        "creator": "me",
        "world_name": "w",
        "depth_prompt": "",
        "character_book_entries": [{"id": 1}],
    }
    mappings = task_flows.build_character_card_field_mappings(fields)
    assert mappings["{{name}}"] == "Alice"
    assert mappings["{{character_book_entries}}"] == [{"id": 1}]

    result = task_flows.build_character_card_success_result("out.json", fields, "ok")
    assert result["success"] is True
    assert result["output_path"] == "out.json"
    assert result["result"] == "ok"
    assert "character_book_entries" not in result["fields_written"]
    assert "description" in result["fields_written"]
    assert "personality" not in result["fields_written"]
