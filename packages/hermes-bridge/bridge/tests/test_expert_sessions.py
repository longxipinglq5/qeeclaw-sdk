from __future__ import annotations


def test_expert_registry_resolves_owner_scoped_marketing_expert():
    from bridge.runtime_facade.experts import ExpertRegistry

    registry = ExpertRegistry.with_builtin_experts()
    expert = registry.get_expert("marketing_strategy_expert")

    assert expert.expert_id == "marketing_strategy_expert"
    assert expert.context_scope == "owner"
    assert expert.hermes_profile == "edge_marketing_strategy"
    assert expert.session_id_for(
        owner_id="owner_1",
        conversation_id="conv_abc",
    ) == "edge:owner_1:expert:marketing_strategy_expert"


def test_expert_registry_resolves_conversation_scoped_sensitive_expert():
    from bridge.runtime_facade.experts import ExpertRegistry

    registry = ExpertRegistry.with_builtin_experts()
    expert = registry.get_expert("hr_compliance_expert")

    assert expert.expert_id == "hr_compliance_expert"
    assert expert.context_scope == "conversation"
    assert expert.hermes_profile == "edge_hr_compliance"
    assert expert.session_id_for(
        owner_id="owner_1",
        conversation_id="conv_hr_001",
    ) == "edge:owner_1:expert:hr_compliance_expert:conv:conv_hr_001"
    assert expert.session_id_for(
        owner_id="owner_1",
        conversation_id="conv_hr_002",
    ) == "edge:owner_1:expert:hr_compliance_expert:conv:conv_hr_002"


def test_linked_session_keeps_conversation_provenance():
    from bridge.runtime_facade.models import LinkedSession

    link = LinkedSession(
        source_session_id="edge:owner_1:supervisor:conv_abc",
        linked_session_id="edge:owner_1:expert:marketing_strategy_expert",
        expert_id="marketing_strategy_expert",
        metadata={"conversation_id": "conv_abc", "owner_id": "owner_1"},
    )

    assert link.metadata["conversation_id"] == "conv_abc"
    assert link.metadata["owner_id"] == "owner_1"
    assert link.model_dump(mode="json")["linked_session_id"] == (
        "edge:owner_1:expert:marketing_strategy_expert"
    )


async def test_post_api_runs_expert_run_creates_linked_expert_session(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(
        app.state.runtime,
        artifact_root_dir=tmp_path,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/runs",
            json={
                "kind": "expert_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "expert_id": "marketing_strategy_expert",
                "agent_profile": "edge_supervisor",
                "input": {
                    "text": "评估朋友圈文案是否太硬广",
                    "artifact_id": "art_moments_001",
                },
                "metadata": {
                    "owner_id": "owner_1",
                    "conversation_id": "conv_abc",
                },
            },
        )
        events_resp = await client.get("/api/runs/run_000001/events")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "expert_run"
    assert body["run_id"] == "run_000001"

    events = events_resp.json()["events"]
    assert [event["type"] for event in events] == [
        "run_started",
        "expert_selected",
        "readiness_check",
        "work_plan",
        "done",
    ]
    expert_selected = events[1]["payload"]
    assert expert_selected["expert_id"] == "marketing_strategy_expert"
    assert expert_selected["linked_session_id"] == (
        "edge:owner_1:expert:marketing_strategy_expert"
    )

    facade = app.state.runtime_facade
    expert_session = facade.sessions.get("edge:owner_1:expert:marketing_strategy_expert")
    supervisor_session = facade.sessions.get("edge:owner_1:supervisor:conv_abc")
    assert expert_session is not None
    assert expert_session.metadata["linked_session"]["source_session_id"] == (
        "edge:owner_1:supervisor:conv_abc"
    )
    assert expert_session.metadata["linked_session"]["metadata"]["conversation_id"] == "conv_abc"
    assert supervisor_session.metadata["expert_summaries"] == [
        {
            "linked_session_id": "edge:owner_1:expert:marketing_strategy_expert",
            "expert_id": "marketing_strategy_expert",
            "expert_summary": "测试回复",
            "source_run_id": "run_000001",
        }
    ]
    assert "评估朋友圈文案是否太硬广" not in str(supervisor_session.metadata["expert_summaries"])


async def test_post_api_runs_expert_run_requires_expert_and_owner_metadata(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(
        app.state.runtime,
        artifact_root_dir=tmp_path,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/runs",
            json={
                "kind": "expert_run",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "input": {"text": "帮我看看"},
                "metadata": {"owner_id": "owner_1"},
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RUN_KIND_UNSUPPORTED"
    assert response.json()["error"]["details"] == {
        "kind": "expert_run",
        "missing": ["expert_id", "conversation_id"],
        "unexpected": [],
    }
