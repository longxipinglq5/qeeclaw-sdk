from __future__ import annotations


def test_session_store_appends_turns_with_content_and_metadata():
    from bridge.runtime_facade.session_store import SessionStore
    from bridge.runtime_facade.store import InMemoryStore

    sessions = SessionStore(InMemoryStore())
    sessions.get_or_create(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
    )

    sessions.append_turn(
        "edge:owner_1:supervisor:conv_abc",
        user_text="帮我总结",
        assistant_text="总结完成",
        metadata={"run_id": "run_000001"},
    )

    assert sessions.get_recent_messages("edge:owner_1:supervisor:conv_abc") == [
        {"role": "user", "content": "帮我总结", "metadata": {"run_id": "run_000001"}},
        {"role": "assistant", "content": "总结完成", "metadata": {"run_id": "run_000001"}},
    ]


def test_session_store_trims_recent_context_by_message_limit():
    from bridge.runtime_facade.session_store import SessionStore
    from bridge.runtime_facade.store import InMemoryStore

    sessions = SessionStore(InMemoryStore())
    sessions.get_or_create(session_id="session_1", agent_profile="edge_supervisor")
    for index in range(4):
        sessions.append_message("session_1", role="user", content=f"message-{index}")

    assert sessions.get_recent_messages("session_1", limit=2) == [
        {"role": "user", "content": "message-2", "metadata": {}},
        {"role": "user", "content": "message-3", "metadata": {}},
    ]


def test_session_store_trims_recent_context_by_token_budget():
    from bridge.runtime_facade.session_store import SessionStore
    from bridge.runtime_facade.store import InMemoryStore

    sessions = SessionStore(InMemoryStore())
    sessions.get_or_create(session_id="session_1", agent_profile="edge_supervisor")
    sessions.append_message("session_1", role="user", content="a" * 40)
    sessions.append_message("session_1", role="assistant", content="b" * 8)
    sessions.append_message("session_1", role="user", content="c" * 8)

    assert sessions.approx_token_count("a" * 40) == 10
    assert sessions.get_recent_messages("session_1", token_budget=4) == [
        {"role": "assistant", "content": "b" * 8, "metadata": {}},
        {"role": "user", "content": "c" * 8, "metadata": {}},
    ]


async def test_platform_conversation_history_prefers_facade_session_messages():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)
    app.state.runtime_facade.sessions.get_or_create(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
    )
    app.state.runtime_facade.sessions.append_turn(
        "edge:owner_1:supervisor:conv_abc",
        user_text="第一轮",
        assistant_text="测试回复",
        metadata={"run_id": "run_000001"},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/platform/conversations/history",
            params={"session_id": "edge:owner_1:supervisor:conv_abc"},
        )

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"role": "user", "content": "第一轮", "metadata": {"run_id": "run_000001"}},
        {"role": "assistant", "content": "测试回复", "metadata": {"run_id": "run_000001"}},
    ]


def test_legacy_employee_session_migration_imports_once_from_session_manager():
    from bridge.runtime_facade.session_migration import migrate_legacy_employee_session
    from bridge.runtime_facade.session_store import SessionStore
    from bridge.runtime_facade.store import InMemoryStore

    class LegacyReader:
        def __init__(self):
            self.reads = 0

        def get_messages(self, session_id):
            self.reads += 1
            assert session_id == "edge:employee_123"
            return [
                {"role": "user", "content": "我们最近主推儿童护眼台灯"},
                {"role": "assistant", "content": "已记录，重点是护眼、学习场景和家长安心。"},
            ]

    sessions = SessionStore(InMemoryStore())
    session = sessions.get_or_create(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
        metadata={
            "legacy_employee_session_id": "edge:employee_123",
            "owner_id": "owner_1",
            "conversation_id": "conv_abc",
        },
    )
    reader = LegacyReader()

    first = migrate_legacy_employee_session(session, sessions, reader)
    second = migrate_legacy_employee_session(sessions.get(session.session_id), sessions, reader)

    assert first["imported_message_count"] == 2
    assert second is None
    assert reader.reads == 1
    assert sessions.get_recent_messages(session.session_id, token_budget=None) == [
        {"role": "user", "content": "我们最近主推儿童护眼台灯", "metadata": {"migration": "legacy_employee_session"}},
        {"role": "assistant", "content": "已记录，重点是护眼、学习场景和家长安心。", "metadata": {"migration": "legacy_employee_session"}},
    ]
    assert sessions.get(session.session_id).metadata["migration"]["from_session_id"] == "edge:employee_123"


async def test_session_context_api_returns_facade_messages_after_invoke():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/invoke",
            json={
                "prompt": "帮我总结这个产品的卖点",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
            },
        )
        response = await client.get(
            "/api/sessions/edge:owner_1:supervisor:conv_abc/context"
        )
        missing_response = await client.get("/api/sessions/session_missing/context")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "edge:owner_1:supervisor:conv_abc"
    assert body["message_count"] == 2
    assert body["approx_token_count"] > 0
    assert body["prompt_prefix_hash"].startswith("sha256:")
    assert body["messages"] == [
        {
            "role": "user",
            "content": "帮我总结这个产品的卖点",
            "metadata": {"run_id": "run_000001"},
        },
        {
            "role": "assistant",
            "content": "测试回复",
            "metadata": {"run_id": "run_000001"},
        },
    ]
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_session_context_api_includes_artifact_summaries_after_skill_run(tmp_path):
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
        await client.post(
            "/api/runs",
            json={
                "kind": "invoke",
                "session_id": "edge:owner_1:supervisor:conv_abc",
                "agent_profile": "edge_supervisor",
                "input": {"text": "帮我生成儿童护眼台灯的小红书"},
                "metadata": {"owner_id": "owner_1", "created_by": "web"},
            },
        )
        response = await client.get(
            "/api/sessions/edge:owner_1:supervisor:conv_abc/context"
        )

    assert response.status_code == 200
    messages = response.json()["messages"]
    artifact_messages = [
        message
        for message in messages
        if message["metadata"].get("section") == "artifact_summaries"
    ]
    assert len(artifact_messages) == 1
    assert "art_run_000002" in artifact_messages[0]["content"]
    assert "小红书种草文" in artifact_messages[0]["content"]
