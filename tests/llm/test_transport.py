from types import SimpleNamespace

from galgame_character_skills.llm.transport import CompletionTransport
import galgame_character_skills.llm.transport as transport_module


def test_complete_with_retry_succeeds_on_first_attempt(monkeypatch):
    called = {}

    def fake_completion(**kwargs):
        called["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(
        transport_module,
        "_get_litellm",
        lambda: SimpleNamespace(completion=fake_completion),
    )

    transport = CompletionTransport()
    result = transport.complete_with_retry(kwargs={"model": "m1"}, max_retries=3)

    assert result == {"ok": True}
    assert called["kwargs"] == {"model": "m1"}


def test_complete_with_retry_retries_and_calls_hooks(monkeypatch):
    state = {"count": 0, "events": []}

    def fake_completion(**kwargs):
        state["count"] += 1
        if state["count"] < 3:
            raise RuntimeError("boom")
        return {"ok": True}

    monkeypatch.setattr(
        transport_module,
        "_get_litellm",
        lambda: SimpleNamespace(completion=fake_completion),
    )
    monkeypatch.setattr(transport_module.time, "sleep", lambda s: state["events"].append(("sleep", s)))

    transport = CompletionTransport()
    result = transport.complete_with_retry(
        kwargs={"model": "m2"},
        max_retries=4,
        on_attempt_failed=lambda attempt, err, retries: state["events"].append(("failed", attempt, str(err), retries)),
        on_retry_wait=lambda wait, attempt, retries: state["events"].append(("wait", wait, attempt, retries)),
        on_success=lambda response: state["events"].append(("success", response)),
        on_final_failure=lambda err: state["events"].append(("final", str(err))),
    )

    assert result == {"ok": True}
    assert state["count"] == 3
    assert ("failed", 0, "boom", 4) in state["events"]
    assert ("failed", 1, "boom", 4) in state["events"]
    assert ("wait", 1, 0, 4) in state["events"]
    assert ("wait", 2, 1, 4) in state["events"]
    assert ("sleep", 1) in state["events"]
    assert ("sleep", 2) in state["events"]
    assert ("success", {"ok": True}) in state["events"]
    assert not any(event[0] == "final" for event in state["events"])


def test_complete_with_retry_returns_none_after_final_failure(monkeypatch):
    state = {"final": None}

    def fake_completion(**kwargs):
        raise RuntimeError("always-fail")

    monkeypatch.setattr(
        transport_module,
        "_get_litellm",
        lambda: SimpleNamespace(completion=fake_completion),
    )
    monkeypatch.setattr(transport_module.time, "sleep", lambda s: None)

    transport = CompletionTransport()
    result = transport.complete_with_retry(
        kwargs={"model": "m3"},
        max_retries=2,
        on_final_failure=lambda err: state.__setitem__("final", str(err)),
    )

    assert result is None
    assert state["final"] == "always-fail"


def test_complete_with_retry_uses_minimum_one_retry(monkeypatch):
    state = {"count": 0}

    def fake_completion(**kwargs):
        state["count"] += 1
        return {"ok": True}

    monkeypatch.setattr(
        transport_module,
        "_get_litellm",
        lambda: SimpleNamespace(completion=fake_completion),
    )

    transport = CompletionTransport()
    result = transport.complete_with_retry(kwargs={"model": "m4"}, max_retries=0)

    assert result == {"ok": True}
    assert state["count"] == 1
