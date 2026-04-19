from galgame_character_skills.api import checkpoint_service as svc


class DummyCheckpointGateway:
    def __init__(self):
        self._ckpt = {"checkpoint_id": "c1", "task_type": "summarize", "input_params": {"role_name": "r"}}
        self._llm_state = {"messages": []}
        self.deleted = False

    def list_checkpoints(self, task_type=None, status=None):
        return [{"checkpoint_id": "c1", "task_type": task_type, "status": status}]

    def load_checkpoint(self, checkpoint_id):
        if checkpoint_id == "missing":
            return None
        return dict(self._ckpt, checkpoint_id=checkpoint_id)

    def load_llm_state(self, checkpoint_id):
        return self._llm_state

    def delete_checkpoint(self, checkpoint_id):
        if checkpoint_id == "missing":
            return False
        self.deleted = True
        return True


def test_list_checkpoints_result():
    gw = DummyCheckpointGateway()

    listed = svc.list_checkpoints_result(gw, task_type="summarize", status="failed")
    assert listed["success"] is True
    assert listed["checkpoints"][0]["task_type"] == "summarize"


def test_get_checkpoint_result_success():
    gw = DummyCheckpointGateway()
    got = svc.get_checkpoint_result(gw, "c1")
    assert got["success"] is True
    assert got["checkpoint"]["checkpoint_id"] == "c1"


def test_get_checkpoint_result_missing():
    gw = DummyCheckpointGateway()
    missing = svc.get_checkpoint_result(gw, "missing")
    assert missing["success"] is False


def test_delete_checkpoint_result_success():
    gw = DummyCheckpointGateway()
    deleted = svc.delete_checkpoint_result(gw, "c1")
    assert deleted["success"] is True


def test_delete_checkpoint_result_missing():
    gw = DummyCheckpointGateway()
    del_missing = svc.delete_checkpoint_result(gw, "missing")
    assert del_missing["success"] is False


def test_resume_checkpoint_result_dispatch(monkeypatch):
    gw = DummyCheckpointGateway()

    monkeypatch.setattr(
        svc,
        "load_resumable_checkpoint",
        lambda _gw, _cid: {"success": True, "checkpoint": {"task_type": "generate_skills", "input_params": {"role_name": "a"}}},
    )

    captured = {}

    def summarize_handler(data):
        captured["summarize"] = data
        return {"success": True, "kind": "summarize"}

    def skills_handler(data):
        captured["skills"] = data
        return {"success": True, "kind": "skills"}

    def card_handler(data):
        captured["card"] = data
        return {"success": True, "kind": "card"}

    result = svc.resume_checkpoint_result(
        ckpt_manager=gw,
        checkpoint_id="c9",
        extra_params={"modelname": "m1"},
        summarize_handler=summarize_handler,
        generate_skills_handler=skills_handler,
        generate_chara_card_handler=card_handler,
    )
    assert result["success"] is True
    assert result["kind"] == "skills"
    assert captured["skills"]["resume_checkpoint_id"] == "c9"
    assert captured["skills"]["modelname"] == "m1"


def test_resume_checkpoint_result_dispatch_summarize(monkeypatch):
    gw = DummyCheckpointGateway()
    monkeypatch.setattr(
        svc,
        "load_resumable_checkpoint",
        lambda _gw, _cid: {"success": True, "checkpoint": {"task_type": "summarize", "input_params": {"role_name": "a"}}},
    )

    def summarize_handler(data):
        return {"success": True, "kind": "summarize", "data": data}

    result = svc.resume_checkpoint_result(
        ckpt_manager=gw,
        checkpoint_id="c2",
        extra_params=None,
        summarize_handler=summarize_handler,
        generate_skills_handler=lambda _: {"success": True, "kind": "skills"},
        generate_chara_card_handler=lambda _: {"success": True, "kind": "card"},
    )
    assert result["success"] is True
    assert result["kind"] == "summarize"
    assert result["data"]["resume_checkpoint_id"] == "c2"


def test_resume_checkpoint_result_dispatch_chara_card(monkeypatch):
    gw = DummyCheckpointGateway()
    monkeypatch.setattr(
        svc,
        "load_resumable_checkpoint",
        lambda _gw, _cid: {"success": True, "checkpoint": {"task_type": "generate_chara_card", "input_params": {"role_name": "a"}}},
    )

    def card_handler(data):
        return {"success": True, "kind": "card", "data": data}

    result = svc.resume_checkpoint_result(
        ckpt_manager=gw,
        checkpoint_id="c3",
        extra_params={"x": 1},
        summarize_handler=lambda _: {"success": True, "kind": "summarize"},
        generate_skills_handler=lambda _: {"success": True, "kind": "skills"},
        generate_chara_card_handler=card_handler,
    )
    assert result["success"] is True
    assert result["kind"] == "card"
    assert result["data"]["resume_checkpoint_id"] == "c3"
    assert result["data"]["x"] == 1


def test_resume_checkpoint_result_returns_load_error(monkeypatch):
    gw = DummyCheckpointGateway()
    monkeypatch.setattr(
        svc,
        "load_resumable_checkpoint",
        lambda _gw, _cid: {"success": False, "message": "bad checkpoint"},
    )
    result = svc.resume_checkpoint_result(gw, "cx", {}, lambda _: {}, lambda _: {}, lambda _: {})
    assert result == {"success": False, "message": "bad checkpoint"}


def test_resume_checkpoint_result_unknown_task(monkeypatch):
    gw = DummyCheckpointGateway()
    monkeypatch.setattr(
        svc,
        "load_resumable_checkpoint",
        lambda _gw, _cid: {"success": True, "checkpoint": {"task_type": "unknown", "input_params": {}}},
    )
    result = svc.resume_checkpoint_result(gw, "cx", {}, lambda _: {}, lambda _: {}, lambda _: {})
    assert result["success"] is False


def test_resume_checkpoint_with_payload_result_passthrough(monkeypatch):
    gw = DummyCheckpointGateway()
    captured = {}

    def fake_resume_checkpoint_result(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr(svc, "resume_checkpoint_result", fake_resume_checkpoint_result)
    result = svc.resume_checkpoint_with_payload_result(
        data={"a": 1},
        checkpoint_id="cp1",
        ckpt_manager=gw,
        summarize_handler=lambda _: {},
        generate_skills_handler=lambda _: {},
        generate_chara_card_handler=lambda _: {},
    )
    assert result["success"] is True
    assert captured["extra_params"] == {"a": 1}
    assert captured["checkpoint_id"] == "cp1"
    assert captured["ckpt_manager"] is gw
