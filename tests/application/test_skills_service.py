from types import SimpleNamespace

from galgame_character_skills.application import skills_context
from galgame_character_skills.application import skills_finalize
from galgame_character_skills.application import skills_service


def test_generate_skills_task_resume_checkpoint_failure_passthrough(monkeypatch):
    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=object(),
    )
    monkeypatch.setattr(
        skills_service,
        "load_resumable_checkpoint",
        lambda gateway, checkpoint_id: {"success": False, "message": "resume failed"},
    )

    result = skills_service.run_generate_skills_task(
        {"role_name": "A", "resume_checkpoint_id": "ckpt-1"},
        runtime,
    )
    assert result == {"success": False, "message": "resume failed"}


def test_generate_skills_task_fails_when_summary_files_missing(monkeypatch):
    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=SimpleNamespace(create_checkpoint=lambda **kwargs: "ckpt-1"),
        estimate_tokens=lambda text: 10,
        get_base_dir=lambda: "/base",
    )
    monkeypatch.setattr(skills_service, "find_role_summary_markdown_files", lambda base, role: [])

    result = skills_service.run_generate_skills_task({"role_name": "A"}, runtime)

    assert result["success"] is False
    assert result["message"] == '未找到角色 "A" 的归纳文件，请先完成归纳'


def test_generate_skills_task_reads_summaries_from_workspace(monkeypatch):
    captured = {}

    class FakeLLMClient:
        def generate_skills_folder_init(self, summaries, role_name, output_language, vndb_data, output_root_dir=""):
            captured["output_root_dir"] = output_root_dir
            return [{"role": "system", "content": "ok"}], []

        def send_message(self, messages, tools, use_counter=False):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="done", tool_calls=[]))])

        def get_tool_response(self, response):
            return []

    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=SimpleNamespace(
            create_checkpoint=lambda **kwargs: "ckpt-1",
            update_progress=lambda *args, **kwargs: None,
            save_llm_state=lambda *args, **kwargs: None,
            mark_completed=lambda *args, **kwargs: None,
        ),
        storage_gateway=SimpleNamespace(makedirs=lambda *args, **kwargs: None),
        estimate_tokens=lambda text: 10,
        llm_gateway=SimpleNamespace(create_client=lambda config: FakeLLMClient()),
        tool_gateway=SimpleNamespace(handle_tool_call=lambda call: "ok"),
    )

    monkeypatch.setattr(skills_service, "get_workspace_summaries_dir", lambda: "D:/workspace/summaries")
    monkeypatch.setattr(skills_service, "get_workspace_skills_dir", lambda: "D:/workspace/skills")
    monkeypatch.setattr(skills_service, "find_role_summary_markdown_files", lambda base, role: [f"{base}/a.md"])
    monkeypatch.setattr(skills_context, "build_full_skill_generation_context", lambda files: "summary")
    monkeypatch.setattr(skills_finalize, "append_vndb_info_to_skill_md", lambda *args, **kwargs: None)
    monkeypatch.setattr(skills_finalize, "create_code_skill_copy", lambda *args, **kwargs: None)

    result = skills_service.run_generate_skills_task({"role_name": "A"}, runtime)

    assert result["success"] is True
    assert captured["output_root_dir"] == "D:/workspace/skills"
