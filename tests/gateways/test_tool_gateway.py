from galgame_character_skills.gateways.tool_gateway import DefaultToolGateway


def test_tool_gateway_delegates_to_tool_handler(monkeypatch):
    called = {}

    def fake_handle_tool_call(tool_call):
        called["handle"] = tool_call
        return {"ok": 1}

    def fake_parse(content):
        called["parse"] = content
        return {"parsed": True}

    def fake_merge(entries):
        called["merge"] = entries
        return {"merged": entries}

    def fake_build(merged_entries, start_id=0):
        called["build"] = (merged_entries, start_id)
        return [{"id": start_id}]

    def fake_fill(template_path, output_path, field_mappings):
        called["fill"] = (template_path, output_path, field_mappings)
        return "filled"

    monkeypatch.setattr(
        "galgame_character_skills.gateways.tool_gateway.ToolHandler.handle_tool_call",
        fake_handle_tool_call,
    )
    monkeypatch.setattr(
        "galgame_character_skills.gateways.tool_gateway.ToolHandler.parse_llm_json_response",
        fake_parse,
    )
    monkeypatch.setattr(
        "galgame_character_skills.gateways.tool_gateway.ToolHandler.merge_lorebook_entries",
        fake_merge,
    )
    monkeypatch.setattr(
        "galgame_character_skills.gateways.tool_gateway.ToolHandler.build_lorebook_entries",
        fake_build,
    )
    monkeypatch.setattr(
        "galgame_character_skills.gateways.tool_gateway.ToolHandler.fill_json_template",
        fake_fill,
    )

    gateway = DefaultToolGateway()
    assert gateway.handle_tool_call({"tool": "x"}) == {"ok": 1}
    assert gateway.parse_llm_json_response("{}") == {"parsed": True}
    assert gateway.merge_lorebook_entries([{"uid": "1"}]) == {"merged": [{"uid": "1"}]}
    assert gateway.build_lorebook_entries({"a": 1}, start_id=9) == [{"id": 9}]
    assert gateway.fill_json_template("a", "b", {"x": "y"}) == "filled"

    assert called["handle"] == {"tool": "x"}
    assert called["parse"] == "{}"
    assert called["merge"] == [{"uid": "1"}]
    assert called["build"] == ({"a": 1}, 9)
    assert called["fill"] == ("a", "b", {"x": "y"})
