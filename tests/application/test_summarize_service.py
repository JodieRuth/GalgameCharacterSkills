from types import SimpleNamespace

from galgame_character_skills.application.summarize import checkpoint as summarize_checkpoint
from galgame_character_skills.application.summarize import service as summarize_service
from galgame_character_skills.application.summarize import slice_executor as summarize_slice_executor
from galgame_character_skills.domain import TASK_TYPE_SUMMARIZE, TASK_TYPE_GENERATE_SKILLS


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

    def send_message(self, messages, tools=None, max_retries=None, use_counter=True):
        return _FakeResponse(content=self.content, tool_calls=self.tool_calls)


def test_run_summarize_task_requires_role_name():
    runtime = SimpleNamespace(clean_vndb_data=lambda x: x)
    result = summarize_service.run_summarize_task({}, runtime)
    assert result["success"] is False
    assert result["message"] == "请输入角色名称"


def test_run_summarize_task_requires_files_for_non_resume():
    runtime = SimpleNamespace(
        clean_vndb_data=lambda x: x,
        checkpoint_gateway=SimpleNamespace(create_checkpoint=lambda **kwargs: "ckpt"),
        llm_gateway=SimpleNamespace(create_request_runtime=lambda total: object()),
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

    result = summarize_slice_executor.process_single_slice(
        args=(0, "slice", "A", "", "out.md", {}, "", "skills", None, "ckpt-1"),
        checkpoint_gateway=FakeCheckpointGateway(),
        llm_gateway=SimpleNamespace(create_client=lambda config, request_runtime=None: _FakeLLMClient()),
        tool_gateway=SimpleNamespace(),
        storage_gateway=FakeStorageGateway(),
    )

    assert result["success"] is True
    assert result["restored"] is True
    assert result["summary"].endswith("...")


def test_process_single_slice_normal_mode_success(monkeypatch):
    monkeypatch.setattr(summarize_slice_executor.time, "sleep", lambda *_: None)

    class FakeCheckpointGateway:
        def get_slice_result(self, checkpoint_id, slice_index):
            return None

        def save_slice_result(self, checkpoint_id, slice_index, content, status):
            self.saved = (checkpoint_id, slice_index, content, status)

        def mark_slice_completed(self, checkpoint_id, slice_index):
            self.marked = (checkpoint_id, slice_index)

    ckpt = FakeCheckpointGateway()
    llm_gateway = SimpleNamespace(create_client=lambda config, request_runtime=None: _FakeLLMClient())

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

    result = summarize_slice_executor.process_single_slice(
        args=(1, "slice", "A", "", "out.md", {}, "", "skills", None, "ckpt-2"),
        checkpoint_gateway=ckpt,
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
    monkeypatch.setattr(summarize_slice_executor.time, "sleep", lambda *_: None)

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
    llm_gateway = SimpleNamespace(create_client=lambda config, request_runtime=None: _FakeLLMClient(content="   "))

    result = summarize_slice_executor.process_single_slice(
        args=(2, "slice", "A", "", "out.md", {}, "", "skills", None, "ckpt-3"),
        checkpoint_gateway=FakeCheckpointGateway(),
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
    content = summarize_checkpoint.build_checkpoint_slice_content(
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
    content = summarize_checkpoint.build_checkpoint_slice_content(
        mode="skills",
        output_file_path="out.md",
        choice=choice,
        result=result,
        storage_gateway=FakeStorageGateway(),
    )
    assert content == "summary-from-result"


def test_sanitize_resume_progress_moves_empty_completed_to_pending():
    calls = {}

    class FakeCheckpointGateway:
        def get_slice_result(self, checkpoint_id, index):
            if index == 0:
                return "ok-content"
            if index == 1:
                return ""
            return None

        def update_progress(self, checkpoint_id, completed_items=None, pending_items=None, **kwargs):
            calls["checkpoint_id"] = checkpoint_id
            calls["completed_items"] = completed_items
            calls["pending_items"] = pending_items

    ckpt = {
        "task_type": TASK_TYPE_SUMMARIZE,
        "progress": {
            "completed_items": [0, 1, 2],
            "pending_items": [3],
        },
    }
    summarize_checkpoint.sanitize_resume_progress(ckpt, FakeCheckpointGateway(), "ckpt-1")

    assert ckpt["progress"]["completed_items"] == [0]
    assert ckpt["progress"]["pending_items"] == [1, 2, 3]
    assert calls["checkpoint_id"] == "ckpt-1"
    assert calls["completed_items"] == [0]
    assert calls["pending_items"] == [1, 2, 3]


def test_sanitize_resume_progress_skips_non_summarize_tasks():
    class FakeCheckpointGateway:
        def get_slice_result(self, checkpoint_id, index):
            raise AssertionError("should not be called")

        def update_progress(self, checkpoint_id, **kwargs):
            raise AssertionError("should not be called")

    ckpt = {
        "task_type": TASK_TYPE_GENERATE_SKILLS,
        "progress": {"completed_items": [0], "pending_items": []},
    }
    summarize_checkpoint.sanitize_resume_progress(ckpt, FakeCheckpointGateway(), "ckpt-2")
    assert ckpt["progress"]["completed_items"] == [0]


def test_build_summary_dir_single_file_uses_workspace_root(monkeypatch):
    monkeypatch.setattr(summarize_service.os, "makedirs", lambda *args, **kwargs: None)
    runtime = SimpleNamespace(get_workspace_summaries_dir=lambda: "D:/workspace/summaries")

    summary_dir = summarize_service._build_summary_dir(["D:/input/story.txt"], "Alice", runtime)

    assert summary_dir.replace("\\", "/") == "D:/workspace/summaries/story_summaries"


def test_build_summary_dir_multi_file_uses_workspace_root(monkeypatch):
    monkeypatch.setattr(summarize_service.os, "makedirs", lambda *args, **kwargs: None)
    runtime = SimpleNamespace(get_workspace_summaries_dir=lambda: "D:/workspace/summaries")

    summary_dir = summarize_service._build_summary_dir(["D:/input/a.txt", "D:/input/b.txt"], "Alice", runtime)

    assert summary_dir.replace("\\", "/") == "D:/workspace/summaries/a_merged_summaries"
