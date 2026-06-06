from __future__ import annotations

from typing import Any

from bridge.runtime_facade.event_bus import EventBus
from bridge.runtime_facade.models import RuntimeEvent, RuntimeRun
from bridge.runtime_facade.run_manager import RunManager
from bridge.runtime_facade.session_store import SessionStore
from bridge.runtime_facade.store import InMemoryStore


class HermesRuntimeFacade:
    """Runtime facade for migrated native FastAPI routes.

    migrated_routes: Plan A migrates only native FastAPI `/invoke` and
    `/invoke/stream`; catch-all `api/legacy.py` remains legacy until a later plan
    explicitly moves each route.
    """

    def __init__(self, legacy_runtime: Any) -> None:
        self._legacy_runtime = legacy_runtime
        self.store = InMemoryStore()
        self.events = EventBus(self.store)
        self.sessions = SessionStore(self.store)
        self.runs = RunManager(store=self.store, event_bus=self.events)

    async def invoke_raw(
        self,
        *,
        session_id: str,
        user_text: str,
        agent_profile: str = "default",
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        self.sessions.get_or_create(
            session_id=session_id,
            agent_profile=agent_profile,
        )
        run = self.runs.start_run(
            session_id=session_id,
            agent_profile=agent_profile,
            input_text=user_text,
        )
        try:
            result = await self._legacy_runtime.invoke_raw(
                session_id=session_id,
                user_text=user_text,
                agent_profile=agent_profile,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            self.runs.fail_run(run.run_id, error=str(exc))
            raise

        self.events.append(
            session_id=session_id,
            run_id=run.run_id,
            type="metering",
            payload=self._usage_from_result(result),
        )
        self.runs.complete_run(
            run.run_id,
            result_text=str(result.get("final_response") or ""),
            usage=self._usage_from_result(result),
        )

        return {
            **result,
            "run_id": run.run_id,
            "session_id": session_id,
            "agent_profile": agent_profile,
        }

    def get_run(self, run_id: str) -> RuntimeRun | None:
        return self.runs.get(run_id)

    def get_run_events(self, run_id: str) -> list[RuntimeEvent]:
        return self.events.list_by_run(run_id)

    @staticmethod
    def _usage_from_result(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "total_tokens": result.get("total_tokens", 0),
        }
