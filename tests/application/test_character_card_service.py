from types import SimpleNamespace

from galgame_character_skills.application.character_card import context as character_card_context
from galgame_character_skills.application.character_card import output as character_card_output
from galgame_character_skills.application.character_card import service as character_card_service


def test_generate_character_card_task_resume_checkpoint_failure_passthrough(monkeypatch):
    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=object(),
    )
    monkeypatch.setattr(
        character_card_service,
        "load_resumable_checkpoint",
        lambda gateway, checkpoint_id: {"success": False, "message": "resume failed"},
    )

    result = character_card_service.run_generate_character_card_task(
        {"role_name": "A", "resume_checkpoint_id": "ckpt-1"},
        runtime,
    )
    assert result == {"success": False, "message": "resume failed"}


def test_generate_character_card_task_fails_when_analysis_file_missing(monkeypatch):
    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=SimpleNamespace(create_checkpoint=lambda **kwargs: "ckpt-1"),
        get_base_dir=lambda: "/base",
        get_workspace_summaries_dir=lambda: "D:/workspace/summaries",
    )
    monkeypatch.setattr(character_card_context, "find_role_analysis_summary_file", lambda base, role: "")

    result = character_card_service.run_generate_character_card_task({"role_name": "A"}, runtime)

    assert result["success"] is False
    assert result["message"] == '未找到角色 "A" 的分析文件，请先完成归纳'


def test_generate_character_card_task_fails_when_analysis_read_error(monkeypatch):
    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=SimpleNamespace(create_checkpoint=lambda **kwargs: "ckpt-1"),
        get_base_dir=lambda: "/base",
        get_workspace_summaries_dir=lambda: "D:/workspace/summaries",
        storage_gateway=SimpleNamespace(read_json=lambda _: (_ for _ in ()).throw(RuntimeError("bad read"))),
    )
    monkeypatch.setattr(
        character_card_context,
        "find_role_analysis_summary_file",
        lambda base, role: "/tmp/analysis.json",
    )

    result = character_card_service.run_generate_character_card_task({"role_name": "A"}, runtime)

    assert result["success"] is False
    assert result["message"] == "读取分析文件失败: bad read"


def test_prepare_output_paths_uses_workspace_cards_dir(monkeypatch):
    runtime = SimpleNamespace(
        storage_gateway=SimpleNamespace(makedirs=lambda *args, **kwargs: None, exists=lambda path: False),
        checkpoint_gateway=SimpleNamespace(get_temp_dir=lambda checkpoint_id: "D:/temp/ckpt"),
        download_vndb_image=lambda url, output_path: False,
        get_workspace_cards_dir=lambda: "D:/workspace/cards",
    )
    request_data = SimpleNamespace(role_name="Alice", vndb_data_raw=None, resume_checkpoint_id="")

    paths = character_card_output.prepare_output_paths(runtime, request_data, "ckpt-1")

    assert paths["output_dir"].replace("\\", "/") == "D:/workspace/cards/Alice-character-card"
    assert paths["json_output_path"].replace("\\", "/") == "D:/workspace/cards/Alice-character-card/Alice_chara_card.json"
