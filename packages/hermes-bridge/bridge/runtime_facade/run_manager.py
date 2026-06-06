from __future__ import annotations

from typing import Any

from bridge.runtime_facade.event_bus import EventBus
from bridge.runtime_facade.models import RunKind, RuntimeRun, RunStatus, utc_now
from bridge.runtime_facade.store import BaseStore


class RunTerminalError(RuntimeError):
    pass


class RunResumeNotAllowedError(RuntimeError):
    pass


class RunManager:
    def __init__(self, *, store: BaseStore, event_bus: EventBus) -> None:
        self._store = store
        self._event_bus = event_bus
        self._next_run_number = 1

    def start_run(
        self,
        *,
        session_id: str,
        agent_profile: str,
        kind: RunKind = RunKind.INVOKE,
        input_text: str | None = None,
        trace_id: str | None = None,
        parent_run_id: str | None = None,
        created_by: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeRun:
        run = RuntimeRun(
            run_id=self._create_run_id(),
            session_id=session_id,
            agent_profile=agent_profile,
            kind=kind,
            status=RunStatus.RUNNING,
            trace_id=trace_id,
            parent_run_id=parent_run_id,
            created_by=created_by,
            source=source,
            input_text=input_text,
            metadata=metadata or {},
        )
        self._store.set("runs", run.run_id, run)
        self._event_bus.append(
            session_id=session_id,
            run_id=run.run_id,
            type="run_started",
            payload={"kind": kind.value, "status": run.status.value},
            trace_id=run.trace_id,
        )
        return run

    def get(self, run_id: str) -> RuntimeRun | None:
        run = self._store.get("runs", run_id)
        return run if isinstance(run, RuntimeRun) else None

    @property
    def next_run_number(self) -> int:
        return self._next_run_number

    def complete_run(
        self,
        run_id: str,
        *,
        result_text: str,
        usage: dict[str, Any] | None = None,
        done_payload: dict[str, Any] | None = None,
    ) -> RuntimeRun:
        run = self._require_run(run_id)
        updated = run.model_copy(
            update={
                "status": RunStatus.COMPLETED,
                "result_text": result_text,
                "usage": usage or {},
                "updated_at": utc_now(),
            }
        )
        self._store.set("runs", run_id, updated)
        self._event_bus.append(
            session_id=updated.session_id,
            run_id=updated.run_id,
            type="done",
            payload=done_payload or {"text": result_text, "usage": updated.usage},
            trace_id=updated.trace_id,
        )
        return updated

    def fail_run(self, run_id: str, *, error: str) -> RuntimeRun:
        run = self._require_run(run_id)
        updated = run.model_copy(
            update={
                "status": RunStatus.FAILED,
                "error": error,
                "updated_at": utc_now(),
            }
        )
        self._store.set("runs", run_id, updated)
        self._event_bus.append(
            session_id=updated.session_id,
            run_id=updated.run_id,
            type="error",
            payload={"error": error},
            trace_id=updated.trace_id,
        )
        return updated

    def cancel_run(self, run_id: str, *, reason: str = "user_cancelled") -> RuntimeRun:
        run = self._require_run(run_id)
        if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            raise RunTerminalError(f"Run is terminal: {run_id}")
        updated = run.model_copy(
            update={
                "status": RunStatus.CANCELLED,
                "updated_at": utc_now(),
            }
        )
        self._store.set("runs", run_id, updated)
        self._event_bus.append(
            session_id=updated.session_id,
            run_id=updated.run_id,
            type="cancelled",
            payload={"reason": reason},
            trace_id=updated.trace_id,
        )
        return updated

    def resume_run(self, run_id: str) -> RuntimeRun:
        run = self._require_run(run_id)
        if run.status not in {
            RunStatus.CANCELLED,
            RunStatus.WAITING_CLARIFICATION,
            RunStatus.WAITING_APPROVAL,
        }:
            raise RunResumeNotAllowedError(f"Run cannot resume from {run.status.value}")
        updated = run.model_copy(
            update={
                "status": RunStatus.RUNNING,
                "updated_at": utc_now(),
            }
        )
        self._store.set("runs", run_id, updated)
        self._event_bus.append(
            session_id=updated.session_id,
            run_id=updated.run_id,
            type="run_resumed",
            payload={"status": updated.status.value},
            trace_id=updated.trace_id,
        )
        return updated

    def _require_run(self, run_id: str) -> RuntimeRun:
        run = self.get(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")
        return run

    def _create_run_id(self) -> str:
        run_id = f"run_{self._next_run_number:06d}"
        self._next_run_number += 1
        return run_id
