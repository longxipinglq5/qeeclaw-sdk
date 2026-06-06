from __future__ import annotations


def _json_datetime(value):
    return value.isoformat().replace("+00:00", "Z")


def test_runtime_models_have_stable_defaults_and_serialization():
    from bridge.runtime_facade import (
        RunKind,
        RunStatus,
        RuntimeEvent,
        RuntimeRun,
        RuntimeSession,
    )

    session = RuntimeSession(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
    )
    assert session.metadata == {}
    assert session.model_dump(mode="json") == {
        "session_id": "edge:owner_1:supervisor:conv_abc",
        "agent_profile": "edge_supervisor",
        "metadata": {},
        "created_at": _json_datetime(session.created_at),
        "updated_at": _json_datetime(session.updated_at),
    }

    run = RuntimeRun(
        run_id="run_inv_001",
        session_id=session.session_id,
        agent_profile=session.agent_profile,
    )
    assert run.kind == RunKind.INVOKE
    assert run.status == RunStatus.QUEUED
    assert run.input_text is None
    assert run.result_text is None
    assert run.error is None
    assert run.usage == {}
    assert run.model_dump(mode="json") == {
        "run_id": "run_inv_001",
        "session_id": "edge:owner_1:supervisor:conv_abc",
        "agent_profile": "edge_supervisor",
        "kind": "invoke",
        "status": "queued",
        "input_text": None,
        "result_text": None,
        "error": None,
        "usage": {},
        "created_at": _json_datetime(run.created_at),
        "updated_at": _json_datetime(run.updated_at),
    }

    event = RuntimeEvent(
        event_id="evt_001",
        session_id=session.session_id,
        run_id=run.run_id,
        type="run_started",
        payload={"kind": RunKind.INVOKE},
    )
    assert event.model_dump(mode="json") == {
        "event_id": "evt_001",
        "session_id": "edge:owner_1:supervisor:conv_abc",
        "run_id": "run_inv_001",
        "type": "run_started",
        "payload": {"kind": "invoke"},
        "created_at": _json_datetime(event.created_at),
    }


def test_runtime_model_enums_cover_plan_values():
    from bridge.runtime_facade import RunKind, RunStatus

    assert {status.value for status in RunStatus} == {
        "queued",
        "running",
        "waiting_approval",
        "waiting_clarification",
        "completed",
        "failed",
        "cancelled",
    }
    assert {kind.value for kind in RunKind} == {
        "invoke",
        "skill_run",
        "expert_run",
        "automation_run",
        "channel_run",
    }
