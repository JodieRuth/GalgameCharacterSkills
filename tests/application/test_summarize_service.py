from types import SimpleNamespace

from galgame_character_skills.application import summarize_service


class _FakeChoice:
    def __init__(self, content="ok", tool_calls=None):
        self.message = SimpleNamespace(content=content, tool_calls=tool_calls)


class _FakeResponse:
    def __init__(self, content="ok", tool_calls=None):
        self.choices = [_FakeChoice(content=content, tool_calls=tool_calls)]


class _FakeLLMClient:
    def __init__(self, content="summary-content", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def summarize_content(self, *args, **kwargs):
        return _FakeResponse(content=self.content, tool_calls=self.tool_calls)

    def summarize_content_for_chara_card(self, *args, **kwargs):
        return _FakeResponse(content='{"character_analysis": {}, "lorebook_entries": []}')


def test_run_summarize_task_requires_role_name():
    runtime = SimpleNamespace(clean_vndb_data=lambda x: x)
    result = summarize_service.run_summarize_task({}, runtime)
    assert result["success"] is False
    assert result["message"] == "请输入角色名称"


def test_run_summarize_task_requires_files_for_non_resume():
    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=SimpleNamespace(create_checkpoint=lambda **kwargs: "ckpt"),
    )
    result = summarize_service.run_summarize_task({"role_name": "A"}, runtime)
    assert result["success"] is False
    assert result["message"] == "请先选择文件"


def test_run_summarize_task_resume_checkpoint_failure_passthrough(monkeypatch):
    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=object(),
    )

    monkeypatch.setattr(
        summarize_service,
        "load_resumable_checkpoint",
        lambda gateway, checkpoint_id: {"success": False, "message": "checkpoint error"},
    )

    result = summarize_service.run_summarize_task(
        {"role_name": "A", "resume_checkpoint_id": "ckpt-1"},
        runtime,
    )
    assert result == {"success": False, "message": "checkpoint error"}


def test_process_single_slice_restores_from_checkpoint_markdown():
    class FakeCheckpointGateway:
        def get_slice_result(self, checkpoint_id, slice_index):
            return "cached"

    class FakeStorageGateway:
        def __init__(self):
            self.content = "x" * 300

        def exists(self, path):
            return True

        def read_text(self, path):
            return self.content

        def write_text(self, path, content):
            self.content = content

    result = summarize_service._process_single_slice(
        args=(0, "slice", "A", "", "out.md", {}, "", "skills", None, "ckpt-1"),
        ckpt_manager=FakeCheckpointGateway(),
        llm_gateway=SimpleNamespace(create_client=lambda config: _FakeLLMClient()),
        tool_gateway=SimpleNamespace(),
        storage_gateway=FakeStorageGateway(),
    )

    assert result["success"] is True
    assert result["restored"] is True
    assert result["summary"].endswith("...")


def test_process_single_slice_normal_mode_success(monkeypatch):
    monkeypatch.setattr(summarize_service.time, "sleep", lambda *_: None)

    class FakeCheckpointGateway:
        def get_slice_result(self, checkpoint_id, slice_index):
            return None

        def save_slice_result(self, checkpoint_id, slice_index, content, status):
            self.saved = (checkpoint_id, slice_index, content, status)

        def mark_slice_completed(self, checkpoint_id, slice_index):
            self.marked = (checkpoint_id, slice_index)

    ckpt = FakeCheckpointGateway()
    llm_gateway = SimpleNamespace(create_client=lambda config: _FakeLLMClient())

    class FakeStorageGateway:
        def __init__(self):
            self.saved = {}

        def exists(self, path):
            return path in self.saved

        def read_text(self, path):
            return self.saved[path]

        def write_text(self, path, content):
            self.saved[path] = content

    storage = FakeStorageGateway()

    result = summarize_service._process_single_slice(
        args=(1, "slice", "A", "", "out.md", {}, "", "skills", None, "ckpt-2"),
        ckpt_manager=ckpt,
        llm_gateway=llm_gateway,
        tool_gateway=SimpleNamespace(handle_tool_call=lambda x: {"ok": True}),
        storage_gateway=storage,
    )

    assert result["success"] is True
    assert result["summary"] == "summary-content"
    assert storage.saved["out.md"] == "summary-content"
    assert ckpt.saved == ("ckpt-2", 1, "summary-content", "completed")
    assert ckpt.marked == ("ckpt-2", 1)


def test_process_single_slice_normal_mode_empty_content_fails(monkeypatch):
    monkeypatch.setattr(summarize_service.time, "sleep", lambda *_: None)

    class FakeCheckpointGateway:
        def get_slice_result(self, checkpoint_id, slice_index):
            return None

        def save_slice_result(self, checkpoint_id, slice_index, content, status):
            raise AssertionError("checkpoint should not be saved for failed slice")

        def mark_slice_completed(self, checkpoint_id, slice_index):
            raise AssertionError("slice should not be marked completed for failed slice")

    class FakeStorageGateway:
        def __init__(self):
            self.saved = {}

        def exists(self, path):
            return path in self.saved

        def write_text(self, path, content):
            self.saved[path] = content

        def read_text(self, path):
            return self.saved[path]

    storage = FakeStorageGateway()
    llm_gateway = SimpleNamespace(create_client=lambda config: _FakeLLMClient(content="   "))

    result = summarize_service._process_single_slice(
        args=(2, "slice", "A", "", "out.md", {}, "", "skills", None, "ckpt-3"),
        ckpt_manager=FakeCheckpointGateway(),
        llm_gateway=llm_gateway,
        tool_gateway=SimpleNamespace(handle_tool_call=lambda x: {"ok": True}),
        storage_gateway=storage,
    )

    assert result["success"] is False
    assert result["summary"] is None
    assert storage.saved == {}


def test_build_checkpoint_slice_content_prefers_written_markdown():
    class FakeStorageGateway:
        def exists(self, path):
            return path == "out.md"

        def read_text(self, path):
            return "saved-from-file"

    choice = _FakeChoice(content="summary-from-llm", tool_calls=None)
    result = {"summary": "summary-from-result"}
    content = summarize_service._build_checkpoint_slice_content(
        mode="skills",
        output_file_path="out.md",
        choice=choice,
        result=result,
        storage_gateway=FakeStorageGateway(),
    )
    assert content == "saved-from-file"


def test_build_checkpoint_slice_content_falls_back_when_file_read_fails():
    class FakeStorageGateway:
        def exists(self, path):
            return True

        def read_text(self, path):
            raise RuntimeError("read failed")

    choice = _FakeChoice(content="summary-from-llm", tool_calls=None)
    result = {"summary": "summary-from-result"}
    content = summarize_service._build_checkpoint_slice_content(
        mode="skills",
        output_file_path="out.md",
        choice=choice,
        result=result,
        storage_gateway=FakeStorageGateway(),
    )
    assert content == "summary-from-result"
