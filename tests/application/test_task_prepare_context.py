from dataclasses import dataclass
from types import SimpleNamespace

from galgame_character_skills.application import task_prepare_context as prepare_module


def test_chain_on_resumed_calls_handlers_in_order():
    calls = []

    def h1(*_):
        calls.append("h1")

    def h2(*_):
        calls.append("h2")

    chained = prepare_module.chain_on_resumed(h1, None, h2)
    chained(object(), object(), object())

    assert calls == ["h1", "h2"]


def test_build_on_resumed_logger_prints_message(capsys):
    logger = prepare_module.build_on_resumed_logger(lambda *_: "resume-log")
    logger(object(), object(), object())
    out = capsys.readouterr().out
    assert "resume-log" in out


def test_build_clean_payload_loader_uses_runtime_cleaner():
    class Request:
        @classmethod
        def from_payload(cls, data, cleaner):
            return {"value": cleaner(data["raw"])}

    loader = prepare_module.build_clean_payload_loader(Request)
    runtime = SimpleNamespace(clean_vndb_data=lambda v: {"cleaned": v})
    request_data = loader({"raw": 1}, runtime)

    assert request_data == {"value": {"cleaned": 1}}


def test_build_prepared_builders_map_common_and_state_fields():
    @dataclass
    class BasicPrepared:
        request_data: object
        config: dict
        checkpoint_id: str

    @dataclass
    class StatePrepared(BasicPrepared):
        messages: list
        iteration: int

    checkpoint_data = SimpleNamespace(
        checkpoint_id="ckpt-1",
        state=SimpleNamespace(messages=["m"], iteration=2),
    )

    basic_builder = prepare_module.build_basic_prepared_builder(BasicPrepared)
    state_builder = prepare_module.build_prepared_state_builder(StatePrepared, ("messages", "iteration"))

    basic = basic_builder("req", {"k": 1}, checkpoint_data)
    state = state_builder("req", {"k": 1}, checkpoint_data)

    assert basic.checkpoint_id == "ckpt-1"
    assert state.messages == ["m"]
    assert state.iteration == 2


def test_prepare_task_context_runs_pipeline_and_resume_hook(monkeypatch):
    called = {"resumed": 0}

    def fake_prepare_request_with_checkpoint(**kwargs):
        return SimpleNamespace(checkpoint_id="ckpt-1", state=SimpleNamespace(v=1), resumed=True), None

    monkeypatch.setattr(prepare_module, "prepare_request_with_checkpoint", fake_prepare_request_with_checkpoint)

    runtime = SimpleNamespace(checkpoint_gateway=object())
    prepared, error = prepare_module.prepare_task_context(
        data={"x": 1},
        runtime=runtime,
        from_payload=lambda data, _runtime: {"payload": data["x"]},
        config_builder=lambda data: {"cfg": data["x"]},
        checkpoint_task_type="t",
        load_resume_state=lambda *_: None,
        build_initial_state=lambda: None,
        load_resumable_checkpoint_fn=lambda *_: None,
        build_prepared=lambda request_data, config, checkpoint_data: (request_data, config, checkpoint_data.checkpoint_id),
        on_resumed=lambda *_: called.__setitem__("resumed", called["resumed"] + 1),
    )

    assert error is None
    assert prepared == ({"payload": 1}, {"cfg": 1}, "ckpt-1")
    assert called["resumed"] == 1


def test_prepare_task_context_stops_on_validation_error():
    runtime = SimpleNamespace(checkpoint_gateway=object())
    prepared, error = prepare_module.prepare_task_context(
        data={"x": 1},
        runtime=runtime,
        from_payload=lambda *_: "req",
        config_builder=lambda *_: {"cfg": 1},
        checkpoint_task_type="t",
        load_resume_state=lambda *_: None,
        build_initial_state=lambda: None,
        load_resumable_checkpoint_fn=lambda *_: None,
        build_prepared=lambda *_: "prepared",
        validate_before_checkpoint=lambda *_: {"success": False, "message": "bad"},
    )

    assert prepared is None
    assert error == {"success": False, "message": "bad"}
