from types import SimpleNamespace

from galgame_character_skills.api.checkpoint_api import CheckpointApi, build_resume_task_handlers
from galgame_character_skills.application import resume_dispatcher as dispatcher_module
from galgame_character_skills.domain import (
    TASK_TYPE_SUMMARIZE,
    TASK_TYPE_GENERATE_SKILLS,
    TASK_TYPE_GENERATE_CHARA_CARD,
)


class DummyCheckpointGateway:
    def __init__(self):
        self._ckpt = {"checkpoint_id": "c1", "task_type": TASK_TYPE_SUMMARIZE, "input_params": {"role_name": "r"}}
        self._llm_state = {"messages": []}

    def list_checkpoints(self, task_type=None, status=None):
        return [{"checkpoint_id": "c1", "task_type": task_type, "status": status}]

    def load_checkpoint(self, checkpoint_id):
        if checkpoint_id == "missing":
            return None
        return dict(self._ckpt, checkpoint_id=checkpoint_id)

    def load_llm_state(self, checkpoint_id):
        return self._llm_state

    def delete_checkpoint(self, checkpoint_id):
        return checkpoint_id != "missing"


def _build_runtime():
    return SimpleNamespace(checkpoint_gateway=DummyCheckpointGateway())


def test_checkpoint_api_list_checkpoints():
    api = CheckpointApi(_build_runtime())

    listed = api.list_checkpoints(task_type=TASK_TYPE_SUMMARIZE, status="failed")

    assert listed["success"] is True
    assert listed["checkpoints"][0]["task_type"] == TASK_TYPE_SUMMARIZE


def test_checkpoint_api_get_checkpoint_missing():
    api = CheckpointApi(_build_runtime())

    result = api.get_checkpoint("missing")

    assert result["success"] is False


def test_checkpoint_api_delete_checkpoint_success():
    api = CheckpointApi(_build_runtime())

    result = api.delete_checkpoint("c1")

    assert result["success"] is True


def test_checkpoint_api_resume_checkpoint(monkeypatch):
    runtime = _build_runtime()
    api = CheckpointApi(runtime)

    monkeypatch.setattr(
        dispatcher_module,
        "load_resumable_checkpoint",
        lambda _gw, _cid: {"success": True, "checkpoint": {"task_type": TASK_TYPE_GENERATE_SKILLS, "input_params": {"role_name": "a"}}},
    )
    api._resume_dispatcher._handlers[TASK_TYPE_GENERATE_SKILLS] = lambda data: {"success": True, "kind": "skills", "data": data}

    result = api.resume_checkpoint("c9", {"model_name": "m1"})

    assert result["success"] is True
    assert result["kind"] == "skills"
    assert result["data"]["resume_checkpoint_id"] == "c9"
    assert result["data"]["model_name"] == "m1"


def test_checkpoint_api_resume_checkpoint_unknown_task(monkeypatch):
    api = CheckpointApi(_build_runtime())

    monkeypatch.setattr(
        dispatcher_module,
        "load_resumable_checkpoint",
        lambda _gw, _cid: {"success": True, "checkpoint": {"task_type": "unknown", "input_params": {}}},
    )

    result = api.resume_checkpoint("cx", {})

    assert result["success"] is False


def test_checkpoint_api_build_resume_task_handlers():
    task_api = SimpleNamespace(
        summarize=lambda data: {"kind": "summarize", "data": data},
        generate_skills_folder=lambda data: {"kind": "skills", "data": data},
        generate_character_card=lambda data: {"kind": "card", "data": data},
    )

    result = build_resume_task_handlers(task_api)

    assert set(result) == {
        TASK_TYPE_SUMMARIZE,
        TASK_TYPE_GENERATE_SKILLS,
        TASK_TYPE_GENERATE_CHARA_CARD,
    }
