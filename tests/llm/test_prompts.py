from galgame_character_skills.llm import prompts


def test_build_summarize_content_payload_includes_language_and_vndb():
    called = {}

    def fake_vndb_section(data, title):
        called["args"] = (data, title)
        return "\n\n## VNDB Character Information\n- Name: Alice\n"

    messages, tools = prompts.build_summarize_content_payload(
        content="story",
        role_name="Alice",
        instruction="be precise",
        output_file_path="out.md",
        output_language="zh",
        vndb_data={"name": "Alice"},
        lang_names={"zh": "中文"},
        format_vndb_section=fake_vndb_section,
    )

    assert tools[0]["function"]["name"] == "write_file"
    assert "markdown format" in tools[0]["function"]["parameters"]["properties"]["content"]["description"]
    assert "You MUST write ALL content in 中文." in messages[0]["content"]
    assert "## VNDB Character Information" in messages[0]["content"]
    assert "Save your summary to: out.md" in messages[1]["content"]
    assert called["args"][1] == "## VNDB Character Information"


def test_build_summarize_chara_card_payload_with_language_override():
    messages, tools = prompts.build_summarize_chara_card_payload(
        content="story",
        role_name="Alice",
        instruction="strict",
        output_file_path="out.json",
        output_language="en",
        vndb_data=None,
        lang_names={"en": "English"},
        format_vndb_section=lambda data, title: "",
    )

    assert tools[0]["function"]["name"] == "write_file"
    assert "JSON format" in tools[0]["function"]["parameters"]["properties"]["content"]["description"]
    assert "OUTPUT LANGUAGE OVERRIDE" in messages[0]["content"]
    assert "ALL output must be in English" in messages[0]["content"]
    assert "extract character analysis and lorebook entries" in messages[1]["content"]


def test_build_generate_skills_folder_init_payload_contains_required_files():
    messages, tools = prompts.build_generate_skills_folder_init_payload(
        summaries="summary text",
        role_name="Alice",
        output_root_dir="D:/workspace/skills",
        output_language="ja",
        vndb_data={"name": "Alice"},
        lang_names={"ja": "日本語"},
        format_vndb_section=lambda data, title: "\n\n## VNDB Character Information\n- Name: Alice\n",
    )

    assert tools[0]["function"]["name"] == "write_file"
    assert "D:/workspace/skills/Alice-skill-main/SKILL.md" in messages[0]["content"]
    assert "resource/relationship_dynamics.md" in messages[0]["content"]
    assert "ALL output must be in 日本語" in messages[0]["content"]
    assert "## VNDB Character Information" in messages[0]["content"]
    assert "Please generate a complete skill folder for character 'Alice'" in messages[1]["content"]


def test_build_compress_content_payload_contains_group_metadata_and_files():
    group_files_content = {"a.md": "A", "b.md": "B"}
    group_info = {"group_index": 1, "total_groups": 3, "file_count": 2}

    messages, tools = prompts.build_compress_content_payload(group_files_content, group_info)

    assert tools[0]["function"]["name"] == "remove_duplicate_sections"
    assert "aggressive text deduplication assistant" in messages[0]["content"]
    assert "group 2 of 3" in messages[1]["content"]
    assert "FILE 1: a.md" in messages[1]["content"]
    assert "FILE 2: b.md" in messages[1]["content"]
