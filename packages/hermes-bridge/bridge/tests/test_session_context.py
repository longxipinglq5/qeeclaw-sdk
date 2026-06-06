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
