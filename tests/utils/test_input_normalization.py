from galgame_character_skills.utils.input_normalization import extract_file_paths


def test_extract_file_paths_prefers_list_field():
    data = {"file_paths": ["a.md", "b.md"], "file_path": "c.md"}
    assert extract_file_paths(data) == ["a.md", "b.md"]


def test_extract_file_paths_falls_back_to_single_path():
    data = {"file_path": "single.md"}
    assert extract_file_paths(data) == ["single.md"]


def test_extract_file_paths_returns_empty_when_no_input():
    assert extract_file_paths({}) == []
