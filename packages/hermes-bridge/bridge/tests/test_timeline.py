from __future__ import annotations


def test_timeline_standard_projection_filters_runtime_noise():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore
    from bridge.runtime_facade.timeline import TimelineStore

    bus = EventBus(InMemoryStore())
    runtime_events = [
        bus.append(session_id="session_1", run_id="run_skill_001", type="run_started"),
        bus.append(session_id="session_1", run_id="run_skill_001", type="token", payload={"text": "正在"}),
        bus.append(session_id="session_1", run_id="run_skill_001", type="reasoning", payload={"text": "..."}),
        bus.append(session_id="session_1", run_id="run_skill_001", type="tool_started", payload={"tool_name": "image_generator"}),
        bus.append(session_id="session_1", run_id="run_skill_001", type="tool_completed", payload={"tool_name": "image_generator"}),
        bus.append(session_id="session_1", run_id="run_skill_001", type="artifact_created", payload={"artifact_id": "art_moments_001"}),
        bus.append(
            session_id="session_1",
            run_id="run_skill_001",
            type="app_result",
            payload={
                "card": {
                    "card_type": "result_preview",
                    "artifact_ids": ["art_moments_001"],
                    "summary": "朋友圈文案和配图已生成",
                    "fallback_text": "朋友圈文案和配图已生成。",
                }
            },
        ),
        bus.append(session_id="session_1", run_id="run_skill_001", type="metering"),
        bus.append(session_id="session_1", run_id="run_skill_001", type="done"),
    ]

    store = TimelineStore()
    for event in runtime_events:
        store.append_from_runtime_event(event)

    page = store.list_session("session_1")

    assert [event.kind for event in page.events] == ["artifact", "card"]
    assert [event.source_event_id for event in page.events] == ["evt_000006", "evt_000007"]
    assert page.events[0].artifact_id == "art_moments_001"
    assert page.events[1].card["card_type"] == "result_preview"
    assert page.next_cursor == "tl_000002"
    assert page.has_more is False


def test_timeline_standard_projection_includes_expected_business_events():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore
    from bridge.runtime_facade.timeline import TimelineStore

    included_types = [
        "artifact_created",
        "app_result",
        "approval_required",
        "clarify_required",
        "work_plan",
        "human_review",
        "memory_candidate",
        "loop_stage_changed",
        "feedback_request",
        "review_card",
        "error",
        "cancelled",
    ]
    bus = EventBus(InMemoryStore())
    store = TimelineStore()
    for event_type in included_types:
        event = bus.append(
            session_id="session_1",
            run_id="run_001",
            type=event_type,
            payload={"cycle_id": "cycle_001", "summary": event_type},
        )
        store.append_from_runtime_event(event)

    assert [event.source_event_type for event in store.list_session("session_1").events] == included_types


def test_timeline_debug_projection_includes_debug_runtime_events():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore
    from bridge.runtime_facade.timeline import TimelineProjectionFilter, TimelineStore

    bus = EventBus(InMemoryStore())
    store = TimelineStore(projection_filter=TimelineProjectionFilter(mode="debug"))
    for event_type in ["capability_selected", "app_started", "done"]:
        store.append_from_runtime_event(
            bus.append(session_id="session_1", run_id="run_001", type=event_type)
        )

    assert [event.source_event_type for event in store.list_session("session_1").events] == [
        "capability_selected",
        "app_started",
        "done",
    ]


def test_timeline_projection_is_idempotent_by_runtime_event_id():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore
    from bridge.runtime_facade.timeline import TimelineStore

    event = EventBus(InMemoryStore()).append(
        session_id="session_1",
        run_id="run_001",
        type="artifact_created",
        payload={"artifact_id": "art_001"},
    )
    store = TimelineStore()

    first = store.append_from_runtime_event(event)
    second = store.append_from_runtime_event(event)

    assert first == second
    assert len(store.list_session("session_1").events) == 1


def test_loop_stage_changes_share_progress_card_id_but_keep_append_only_events():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore
    from bridge.runtime_facade.timeline import TimelineStore

    bus = EventBus(InMemoryStore())
    store = TimelineStore()
    first = store.append_from_runtime_event(
        bus.append(
            session_id="session_1",
            run_id="run_auto_001",
            type="loop_stage_changed",
            payload={"cycle_id": "cycle_content_001", "stage": "generating"},
        )
    )
    second = store.append_from_runtime_event(
        bus.append(
            session_id="session_1",
            run_id="run_auto_001",
            type="loop_stage_changed",
            payload={"cycle_id": "cycle_content_001", "stage": "awaiting_review"},
        )
    )

    assert first is not None
    assert second is not None
    assert first.card["card_id"] == "card_progress_cycle_content_001"
    assert second.card["card_id"] == "card_progress_cycle_content_001"
    assert first.event_id == "tl_000001"
    assert second.event_id == "tl_000002"
    assert first.cursor == "tl_000001"
    assert second.cursor == "tl_000002"
    assert first.source_event_id == "evt_000001"
    assert second.source_event_id == "evt_000002"


def test_event_bus_can_project_runtime_events_to_timeline_store():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore
    from bridge.runtime_facade.timeline import TimelineStore

    timeline = TimelineStore()
    bus = EventBus(InMemoryStore(), timeline_store=timeline)

    bus.append(
        session_id="session_1",
        run_id="run_skill_001",
        type="artifact_created",
        payload={"artifact_id": "art_001"},
    )

    assert [event.artifact_id for event in timeline.list_session("session_1").events] == ["art_001"]


async def test_timeline_api_lists_events_with_cursor_pagination(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    facade = app.state.runtime_facade
    facade.events.append(session_id="edge:owner_1:supervisor:conv_abc", run_id="run_001", type="artifact_created", payload={"artifact_id": "art_001"})
    facade.events.append(session_id="edge:owner_1:supervisor:conv_abc", run_id="run_001", type="app_result", payload={"card": {"card_type": "result_preview", "summary": "done", "artifact_ids": ["art_001"]}})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/api/sessions/edge:owner_1:supervisor:conv_abc/timeline?limit=1")
        second = await client.get(
            "/api/sessions/edge:owner_1:supervisor:conv_abc/timeline?cursor=tl_000001&limit=50",
            headers={"Last-Event-ID": "tl_999999"},
        )

    assert first.status_code == 200
    assert first.json()["events"][0]["event_id"] == "tl_000001"
    assert first.json()["next_cursor"] == "tl_000001"
    assert first.json()["has_more"] is True
    assert second.status_code == 200
    assert [event["event_id"] for event in second.json()["events"]] == ["tl_000002"]


async def test_timeline_read_receipts_only_update_receipt_fields(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    session_id = "edge:owner_1:supervisor:conv_abc"
    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    facade = app.state.runtime_facade
    facade.events.append(session_id=session_id, run_id="run_001", type="artifact_created", payload={"artifact_id": "art_001"})
    before = facade.timeline.list_session(session_id).events[0].model_dump(mode="json")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/sessions/{session_id}/timeline/read-receipts",
            json={"reader_id": "owner_1", "event_ids": ["tl_000001"], "read_at": "2026-06-06T10:00:00+00:00"},
        )

    assert response.status_code == 200
    updated = response.json()["events"][0]
    assert updated["read_at"] == "2026-06-06T10:00:00+00:00"
    assert updated["seen_by"] == ["owner_1"]
    for key in ["event_id", "source_event_id", "cursor", "artifact_id", "kind"]:
        assert updated[key] == before[key]


async def test_timeline_read_receipts_reject_cross_owner_reader(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    session_id = "edge:owner_1:supervisor:conv_abc"
    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)
    app.state.runtime_facade.events.append(session_id=session_id, run_id="run_001", type="artifact_created", payload={"artifact_id": "art_001"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/sessions/{session_id}/timeline/read-receipts",
            json={"reader_id": "other_owner", "event_ids": ["tl_000001"]},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TIMELINE_READER_MISMATCH"


async def test_timeline_stream_starts_with_keep_alive_and_stays_open(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    session_id = "edge:owner_1:supervisor:conv_abc"
    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime, artifact_root_dir=tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", f"/api/sessions/{session_id}/timeline/stream") as response:
            body = await response.aread()

    assert response.status_code == 200
    assert body.decode().startswith(": keep-alive")
