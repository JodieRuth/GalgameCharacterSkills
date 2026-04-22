import os

from galgame_character_skills.files import summary_discovery


def test_discover_summary_roles_collects_md_and_json_roles(monkeypatch):
    walk_result = [
        ("/base", ["a_summaries", "other"], []),
        ("/base/a_summaries", [], []),
    ]

    summaries_dir = os.path.join("/base", "a_summaries")
    listing = {
        summaries_dir: [
            "slice_001_Alice.md",
            "slice_002_Alice.md",
            "slice_001_Bob.json",
            "Alice_analysis_summary.json",
        ]
    }

    monkeypatch.setattr(summary_discovery.os, "walk", lambda base_dir: walk_result)
    monkeypatch.setattr(summary_discovery.os, "listdir", lambda path: listing[path])

    result = summary_discovery.discover_summary_roles("/base")

    assert result["skills_roles"] == ["Alice"]
    assert result["chara_card_roles"] == ["Alice", "Bob"]
    assert result["roles"] == ["Alice", "Bob"]


def test_find_summary_files_for_role_by_mode(monkeypatch):
    monkeypatch.setattr(
        summary_discovery,
        "_iter_summary_dirs",
        lambda base_dir: [os.path.join("/base", "a_summaries")],
    )
    monkeypatch.setattr(
        summary_discovery.os,
        "listdir",
        lambda path: ["slice_001_Alice.md", "slice_002_Alice.json", "slice_003_Other.md"],
    )

    md_files = summary_discovery.find_summary_files_for_role("/base", "Alice", mode="skills")
    json_files = summary_discovery.find_summary_files_for_role("/base", "Alice", mode="chara_card")

    assert md_files == [os.path.join("/base", "a_summaries", "slice_001_Alice.md")]
    assert json_files == [os.path.join("/base", "a_summaries", "slice_002_Alice.json")]


def test_find_role_summary_markdown_files_handles_listdir_error(monkeypatch):
    monkeypatch.setattr(summary_discovery, "_iter_summary_dirs", lambda base_dir: ["/bad"])
    monkeypatch.setattr(
        summary_discovery.os,
        "listdir",
        lambda path: (_ for _ in ()).throw(PermissionError("denied")),
    )

    assert summary_discovery.find_role_summary_markdown_files("/base", "Alice") == []


def test_find_role_analysis_summary_file_returns_first_existing(monkeypatch):
    monkeypatch.setattr(
        summary_discovery,
        "_iter_summary_dirs",
        lambda base_dir: [os.path.join("/d1"), os.path.join("/d2")],
    )

    def fake_exists(path):
        return path == os.path.join("/d2", "Alice_analysis_summary.json")

    monkeypatch.setattr(summary_discovery.os.path, "exists", fake_exists)

    result = summary_discovery.find_role_analysis_summary_file("/base", "Alice")
    assert result == os.path.join("/d2", "Alice_analysis_summary.json")
