from datetime import datetime

import galgame_character_skills.llm.character_card_fields as character_card_fields


def test_build_write_field_tools_schema():
    tools = character_card_fields.build_write_field_tools()
    assert len(tools) == 1
    function_def = tools[0]["function"]
    assert function_def["name"] == "write_field"
    enum_values = function_def["parameters"]["properties"]["field_name"]["enum"]
    assert "description" in enum_values
    assert "depth_prompt" in enum_values


def test_build_initial_character_card_fields_with_vndb_data():
    fields = character_card_fields.build_initial_character_card_fields(
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
    character_card_fields.apply_checkpoint_fields(fields, ckpt)
    assert fields["name"] == "Alice2"
    assert fields["description"] == "desc"
    assert fields["character_book_entries"] == [{"id": 1}]


def test_build_character_card_messages_resuming():
    messages, iteration = character_card_fields.build_character_card_messages(
        is_resuming=True,
        ckpt_messages=[{"role": "assistant", "content": "x"}],
        ckpt_iteration_count=4,
        system_prompt="sys",
        role_name="Alice",
    )
    assert messages == [{"role": "assistant", "content": "x"}]
    assert iteration == 4


def test_build_character_card_messages_non_resuming(monkeypatch):
    monkeypatch.setattr(character_card_fields, "build_character_card_user_prompt", lambda role: f"user:{role}")
    messages, iteration = character_card_fields.build_character_card_messages(
        is_resuming=False,
        ckpt_messages=[],
        ckpt_iteration_count=None,
        system_prompt="sys2",
        role_name="Bob",
    )
    assert messages[0] == {"role": "system", "content": "sys2"}
    assert messages[1] == {"role": "user", "content": "user:Bob"}
    assert iteration == 0


def test_build_character_card_template_path():
    path = character_card_fields.build_character_card_template_path()
    assert path.endswith("utils\\chara_card_template.json") or path.endswith("utils/chara_card_template.json")


def test_build_character_card_field_mappings():
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
    mappings = character_card_fields.build_character_card_field_mappings(fields)
    assert mappings["{{name}}"] == "Alice"
    assert mappings["{{character_book_entries}}"] == [{"id": 1}]


def test_build_character_card_success_result():
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
    result = character_card_fields.build_character_card_success_result("out.json", fields, "ok")
    assert result["success"] is True
    assert result["output_path"] == "out.json"
    assert result["result"] == "ok"
    assert "character_book_entries" not in result["fields_written"]
    assert "description" in result["fields_written"]
    assert "personality" not in result["fields_written"]
