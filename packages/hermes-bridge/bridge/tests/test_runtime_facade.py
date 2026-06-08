from __future__ import annotations

import asyncio


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
        "trace_id": None,
        "parent_run_id": None,
        "created_by": None,
        "source": None,
        "input_text": None,
        "result_text": None,
        "error": None,
        "usage": {},
        "metadata": {},
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
        "trace_id": None,
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


def test_session_id_builder_creates_canonical_ids():
    from bridge.runtime_facade.session_ids import SessionIdBuilder

    assert (
        SessionIdBuilder.supervisor("owner_1", "conv_abc")
        == "edge:owner_1:supervisor:conv_abc"
    )
    assert (
        SessionIdBuilder.expert("owner_1", "marketing_strategy_expert")
        == "edge:owner_1:expert:marketing_strategy_expert"
    )
    assert (
        SessionIdBuilder.channel("owner_1", "wechat", "room_42")
        == "edge:owner_1:channel:wechat:room_42"
    )
    assert (
        SessionIdBuilder.automation("owner_1", "marketing_employee", "goal_001")
        == "edge:owner_1:automation:marketing_employee:goal_001"
    )


def test_in_memory_store_contract_for_phase_one():
    from bridge.runtime_facade.store import InMemoryStore

    store = InMemoryStore()
    store.set("sessions", "session_1", {"message_count": 1})
    store.set("sessions", "session_2", {"message_count": 2})

    assert store.get("sessions", "session_1") == {"message_count": 1}
    assert store.get("sessions", "missing") is None
    assert store.list("sessions") == [
        {"message_count": 1},
        {"message_count": 2},
    ]
    assert store.persist() == {
        "persisted": False,
        "reason": "in_memory_store",
    }
    assert store.restore() == {
        "restored": False,
        "reason": "in_memory_store",
    }
    assert store.retention.event_retention_after_terminal_hours == 24
    assert store.retention.timeline_retention_days is None


def test_event_bus_appends_and_reads_ordered_run_events():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.store import InMemoryStore

    bus = EventBus(InMemoryStore())
    first = bus.append(
        session_id="session_1",
        run_id="run_1",
        type="run_started",
        payload={"status": "running"},
    )
    second = bus.append(
        session_id="session_1",
        run_id="run_1",
        type="token",
        payload={"text": "第一句"},
    )
    bus.append(
        session_id="session_1",
        run_id="run_2",
        type="run_started",
        payload={},
    )

    assert first.event_id == "evt_000001"
    assert second.event_id == "evt_000002"
    assert [event.type for event in bus.list_by_run("run_1")] == [
        "run_started",
        "token",
    ]
    assert [event.event_id for event in bus.list_by_run("run_1", after_event_id=first.event_id)] == [
        "evt_000002",
    ]


def test_renderable_reply_text_ignores_skill_view_metadata_tool_output():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    response_text = HermesRuntimeFacade._renderable_reply_text(
        {
            "final_response": (
                "```json\n"
                '{"moments_copy":"雨天也别让护理间闲着，今天到店护理满99减20。"}'
                "\n```"
            ),
            "messages": [
                {
                    "role": "tool",
                    "tool_name": "skill_view",
                    "name": "skill_view",
                    "content": (
                        '{"success":true,"name":"weather-day-promo-generator",'
                        '"skill_dir":"/skills/weather-day-promo-generator",'
                        '"content":"# 雨天拉客\\n这是工具定义，不是生成结果"}'
                    ),
                    "tool_call_id": "call_skill_view_001",
                }
            ],
        }
    )

    assert "weather-day-promo-generator" not in response_text
    assert "skill_dir" not in response_text
    assert "moments_copy" in response_text


def test_renderable_reply_text_ignores_missing_internal_tool_output():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    response_text = HermesRuntimeFacade._renderable_reply_text(
        {
            "final_response": "已经生成海报方案，请打开工具箱确认后出图。",
            "messages": [
                {
                    "role": "tool",
                    "tool_name": "bash",
                    "name": "bash",
                    "content": (
                        "Tool 'bash' does not exist. Available tools: memory, "
                        "session_search, skill_view, image_generate"
                    ),
                    "tool_call_id": "call_bash_001",
                }
            ],
        }
    )

    assert response_text == "已经生成海报方案，请打开工具箱确认后出图。"
    assert "Tool 'bash' does not exist" not in response_text
    assert '"card_type": "result_preview"' not in response_text


def test_renderable_reply_text_ignores_memory_tool_output():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    response_text = HermesRuntimeFacade._renderable_reply_text(
        {
            "final_response": "好，记下了。你接下来想做海报还是朋友圈文案？",
            "messages": [
                {
                    "role": "tool",
                    "tool_name": "memory",
                    "name": "memory",
                    "content": (
                        '{"success":true,"target":"user","entries":["真实姓名：林岚。"],'
                        '"usage":"23%","entry_count":8,"message":"Entry added."}'
                    ),
                    "tool_call_id": "call_memory_001",
                }
            ],
        }
    )

    assert response_text == "好，记下了。你接下来想做海报还是朋友圈文案？"
    assert "真实姓名" not in response_text
    assert '"card_type": "result_preview"' not in response_text


def test_renderable_reply_text_hides_image_runtime_implementation_leak():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    response_text = HermesRuntimeFacade._renderable_reply_text(
        {
            "final_response": (
                "我现在没有生图执行环境（ComfyUI 没装、也没有终端权限），"
                "所以没法直接跑图。"
            )
        }
    )

    assert "ComfyUI" not in response_text
    assert "终端权限" not in response_text
    assert "生图执行环境" not in response_text
    assert "工具箱" in response_text


def test_session_store_creates_updates_and_preserves_message_order():
    from bridge.runtime_facade.session_store import SessionStore
    from bridge.runtime_facade.store import InMemoryStore

    sessions = SessionStore(InMemoryStore())
    session = sessions.get_or_create(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
        metadata={"owner_id": "owner_1"},
    )

    assert session.session_id == "edge:owner_1:supervisor:conv_abc"
    assert session.agent_profile == "edge_supervisor"
    assert session.metadata == {"owner_id": "owner_1"}

    updated = sessions.get_or_create(
        session_id=session.session_id,
        agent_profile="edge_supervisor",
        metadata={"conversation_id": "conv_abc"},
    )
    assert updated.metadata == {
        "owner_id": "owner_1",
        "conversation_id": "conv_abc",
    }
    assert updated.updated_at >= session.updated_at

    sessions.append_message(session.session_id, role="user", text="第一句")
    sessions.append_message(session.session_id, role="assistant", text="第二句")

    assert sessions.list_messages(session.session_id) == [
        {"role": "user", "text": "第一句"},
        {"role": "assistant", "text": "第二句"},
    ]


def test_run_manager_creates_runs_and_emits_lifecycle_events():
    from bridge.runtime_facade.event_bus import EventBus
    from bridge.runtime_facade.models import RunStatus
    from bridge.runtime_facade.run_manager import RunManager
    from bridge.runtime_facade.store import InMemoryStore

    store = InMemoryStore()
    events = EventBus(store)
    runs = RunManager(store=store, event_bus=events)

    run = runs.start_run(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
        input_text="帮我总结",
    )
    assert run.run_id == "run_000001"
    assert run.status == RunStatus.RUNNING
    assert run.input_text == "帮我总结"
    assert [event.type for event in events.list_by_run(run.run_id)] == ["run_started"]

    completed = runs.complete_run(
        run.run_id,
        result_text="总结完成",
        usage={"input_tokens": 12, "output_tokens": 4},
    )
    assert completed.status == RunStatus.COMPLETED
    assert completed.result_text == "总结完成"
    assert completed.usage == {"input_tokens": 12, "output_tokens": 4}
    assert [event.type for event in events.list_by_run(run.run_id)] == [
        "run_started",
        "done",
    ]

    failed = runs.start_run(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
    )
    failed = runs.fail_run(failed.run_id, error="provider failed")
    assert failed.status == RunStatus.FAILED
    assert failed.error == "provider failed"
    assert [event.type for event in events.list_by_run(failed.run_id)] == [
        "run_started",
        "error",
    ]


class FakeLegacyRuntime:
    def __init__(self, response_overrides=None):
        self.invoke_calls = []
        self.stream_calls = []
        self.response_overrides = response_overrides or {}

    async def invoke_raw(self, **kwargs):
        self.invoke_calls.append(kwargs)
        response = {
            "final_response": "测试回复",
            "completed": True,
            "failed": False,
            "model": "deepseek-v4-pro",
            "provider": "deepseek",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }
        response.update(self.response_overrides)
        return response

    async def stream_raw(self, **kwargs):
        from bridge.runtime import StreamHandle

        self.stream_calls.append(kwargs)
        queue = asyncio.Queue()

        async def _run():
            await queue.put(("delta", "第一句"))
            await queue.put(("delta", "第二句"))
            await queue.put(("done", "最终回复"))

        return StreamHandle(queue=queue, task=asyncio.create_task(_run()))


async def test_facade_invoke_raw_wraps_legacy_runtime_and_records_events():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime()
    facade = HermesRuntimeFacade(legacy)

    result = await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="你好",
        agent_profile="edge_supervisor",
        system_prompt="你是主管",
    )

    assert legacy.invoke_calls == [
        {
            "session_id": "edge:owner_1:supervisor:conv_abc",
            "user_text": "你好",
            "agent_profile": "edge_supervisor",
            "system_prompt": "你是主管",
            "conversation_history": [],
        }
    ]
    assert result["final_response"] == "测试回复"
    assert result["run_id"] == "run_000001"
    assert result["session_id"] == "edge:owner_1:supervisor:conv_abc"
    assert result["agent_profile"] == "edge_supervisor"

    run = facade.get_run("run_000001")
    assert run is not None
    assert run.result_text == "测试回复"
    event_types = [event.type for event in facade.get_run_events("run_000001")]
    assert event_types[0] == "run_started"
    assert event_types.count("message") == 2
    assert "metering" in event_types
    assert "done" in event_types


async def test_edge_supervisor_image_request_suggests_toolbox_when_image_generate_unavailable(monkeypatch):
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime()
    facade = HermesRuntimeFacade(legacy)
    monkeypatch.setattr(facade, "_image_generate_tool_available", lambda: False)

    result = await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="帮我生成一张小学生护脊书包的产品海报",
        agent_profile="edge_supervisor",
    )

    assert legacy.invoke_calls == []
    assert result["final_response"] == "我可以帮你打开海报工具箱，把主题和已知信息先填好，你确认后再生成。"
    assert result["ui_intent"] == {
        "type": "toolbox.suggest_open",
        "summary": "我可以帮你打开海报工具箱，把主题和已知信息先填好，你确认后再生成。",
        "appId": "poster-generator",
        "appName": "海报生成器",
        "skillId": "poster-generator",
        "prefilled": {
            "purpose": "产品介绍海报",
            "theme": "小学生护脊书包的产品海报",
            "business_info": "小学生护脊书包",
        },
        "missingFields": ["视觉风格", "画面比例"],
        "confidence": "high",
        "requiresConfirmation": True,
        "autoRun": False,
        "useKnowledgeDefault": True,
    }

    events = facade.get_run_events("run_000001")
    event_types = [event.type for event in events]
    assert "tool_call.started" not in event_types
    assert "tool_call.failed" not in event_types
    done = next(event for event in events if event.type == "done")
    assert done.payload["ui_intent"] == result["ui_intent"]
    assert "bash" not in done.payload["text"]
    assert "ComfyUI" not in done.payload["text"]


async def test_edge_supervisor_image_request_prefills_pronoun_from_session_context(monkeypatch):
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime({"final_response": "收到，记下这个产品。"})
    facade = HermesRuntimeFacade(legacy)

    await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="我的产品是小学生人体工学护脊书包。",
        agent_profile="edge_supervisor",
    )
    monkeypatch.setattr(facade, "_image_generate_tool_available", lambda: False)

    result = await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="帮我给它做一张产品海报",
        agent_profile="edge_supervisor",
    )

    prefilled = result["ui_intent"]["prefilled"]
    assert prefilled["theme"] == "小学生人体工学护脊书包的产品海报"
    assert prefilled["business_info"] == "小学生人体工学护脊书包"


async def test_edge_supervisor_english_image_request_suggests_toolbox(monkeypatch):
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime()
    facade = HermesRuntimeFacade(legacy)
    monkeypatch.setattr(facade, "_image_generate_tool_available", lambda: False)

    result = await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="Generate a product poster for an ergonomic backpack.",
        agent_profile="edge_supervisor",
    )

    prefilled = result["ui_intent"]["prefilled"]
    assert result["ui_intent"]["type"] == "toolbox.suggest_open"
    assert prefilled["theme"] == "an ergonomic backpack product poster"
    assert prefilled["business_info"] == "an ergonomic backpack"


async def test_edge_supervisor_english_image_request_prefills_pronoun_from_session_context(monkeypatch):
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime({"final_response": "Got it."})
    facade = HermesRuntimeFacade(legacy)

    await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="My product is an ergonomic backpack for primary school students.",
        agent_profile="edge_supervisor",
    )
    monkeypatch.setattr(facade, "_image_generate_tool_available", lambda: False)

    result = await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="Generate a product poster for it.",
        agent_profile="edge_supervisor",
    )

    prefilled = result["ui_intent"]["prefilled"]
    assert prefilled["theme"] == "an ergonomic backpack for primary school students product poster"
    assert prefilled["business_info"] == "an ergonomic backpack for primary school students"


async def test_facade_stream_raw_wraps_legacy_stream_and_records_events():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime()
    facade = HermesRuntimeFacade(legacy)

    handle = await facade.stream_raw(
        session_id="edge:owner_1:supervisor:conv_stream",
        user_text="写三句朋友圈文案",
        agent_profile="edge_supervisor",
        system_prompt=None,
    )

    chunks = []
    while True:
        event_type, payload = await handle.queue.get()
        chunks.append((event_type, payload))
        if event_type in {"done", "error"}:
            break

    assert chunks == [
        ("delta", "第一句"),
        ("delta", "第二句"),
        ("done", "最终回复"),
    ]
    assert legacy.stream_calls == [
        {
            "session_id": "edge:owner_1:supervisor:conv_stream",
            "user_text": "写三句朋友圈文案",
            "agent_profile": "edge_supervisor",
            "system_prompt": None,
            "conversation_history": [],
        }
    ]
    assert [event.type for event in facade.get_run_events("run_000001")] == [
        "run_started",
        "token",
        "token",
        "done",
    ]


async def test_facade_invoke_raw_uses_session_store_as_canonical_history():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime()
    facade = HermesRuntimeFacade(legacy)

    await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="第一轮",
        agent_profile="edge_supervisor",
    )
    await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="第二轮",
        agent_profile="edge_supervisor",
    )

    assert legacy.invoke_calls[0]["conversation_history"] == []
    assert legacy.invoke_calls[1]["conversation_history"] == [
        {"role": "user", "content": "第一轮", "metadata": {"run_id": "run_000001"}},
        {"role": "assistant", "content": "测试回复", "metadata": {"run_id": "run_000001"}},
    ]
    assert facade.sessions.get_recent_messages("edge:owner_1:supervisor:conv_abc") == [
        {"role": "user", "content": "第一轮", "metadata": {"run_id": "run_000001"}},
        {"role": "assistant", "content": "测试回复", "metadata": {"run_id": "run_000001"}},
        {"role": "user", "content": "第二轮", "metadata": {"run_id": "run_000002"}},
        {"role": "assistant", "content": "测试回复", "metadata": {"run_id": "run_000002"}},
    ]


async def test_run_and_session_rest_apis_read_facade_state():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)
    await app.state.runtime_facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="你好",
        agent_profile="edge_supervisor",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        run_resp = await client.get("/api/runs/run_000001")
        events_resp = await client.get("/api/runs/run_000001/events")
        sessions_resp = await client.get("/api/sessions")
        session_resp = await client.get("/api/sessions/edge:owner_1:supervisor:conv_abc")
        missing_resp = await client.get("/api/runs/run_missing")

    assert run_resp.status_code == 200
    assert run_resp.json()["run"]["run_id"] == "run_000001"
    assert events_resp.status_code == 200
    event_types = [event["type"] for event in events_resp.json()["events"]]
    assert event_types[0] == "run_started"
    assert event_types.count("message") == 2
    assert "metering" in event_types
    assert "done" in event_types
    assert sessions_resp.status_code == 200
    assert sessions_resp.json()["sessions"][0]["session_id"] == "edge:owner_1:supervisor:conv_abc"
    assert session_resp.status_code == 200
    assert session_resp.json()["session"]["agent_profile"] == "edge_supervisor"
    assert missing_resp.status_code == 404


async def test_run_event_sse_stream_replays_events_and_honors_last_event_id():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)
    await app.state.runtime_facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="你好",
        agent_profile="edge_supervisor",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        stream_resp = await client.get("/api/runs/run_000001/events/stream")
        replay_resp = await client.get(
            "/api/runs/run_000001/events/stream",
            headers={"Last-Event-ID": "evt_000001"},
        )

    assert stream_resp.status_code == 200
    assert "text/event-stream" in stream_resp.headers["content-type"]
    assert "id: evt_000001" in stream_resp.text
    assert "event: run_started" in stream_resp.text
    assert "event: metering" in stream_resp.text
    assert "event: done" in stream_resp.text

    assert replay_resp.status_code == 200
    assert "id: evt_000001" not in replay_resp.text
    assert "id: evt_000002" in replay_resp.text
    assert "id: evt_000003" in replay_resp.text


async def test_facade_normalizes_prompt_cache_usage_in_metering_and_done_events():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime(
        {
            "prompt_cache_hit_tokens": 80,
            "prompt_cache_miss_tokens": 20,
            "prompt_tokens": 100,
            "completion_tokens": 25,
        }
    )
    facade = HermesRuntimeFacade(legacy)

    await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="你好",
        agent_profile="edge_supervisor",
    )

    events = facade.get_run_events("run_000001")
    metering = next(event for event in events if event.type == "metering")
    done = next(event for event in events if event.type == "done")

    assert metering.payload["usage"]["cache_read_tokens"] == 80
    assert metering.payload["usage"]["cache_write_tokens"] == 20
    assert metering.payload["usage"]["cache_hit_percent"] == 80.0
    assert metering.payload["usage"]["prompt_prefix_hash"].startswith("sha256:")
    assert metering.payload["cache_prefix_changed"] is False
    assert done.payload["usage"] == metering.payload["usage"]


async def test_facade_marks_cache_prefix_changed_when_stable_inputs_change():
    from bridge.runtime_facade.facade import HermesRuntimeFacade

    legacy = FakeLegacyRuntime()
    facade = HermesRuntimeFacade(legacy)
    facade.sessions.get_or_create(
        session_id="edge:owner_1:supervisor:conv_abc",
        agent_profile="edge_supervisor",
        metadata={
            "capability_manifest": [
                {"capability_id": "xiaohongshu_note_writer", "version": "2026-06-06"}
            ]
        },
    )

    await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="第一轮",
        agent_profile="edge_supervisor",
    )
    first_metering = next(event for event in facade.get_run_events("run_000001") if event.type == "metering")

    facade.sessions.update_metadata(
        "edge:owner_1:supervisor:conv_abc",
        {
            "capability_manifest": [
                {"capability_id": "xiaohongshu_note_writer", "version": "2026-06-07"}
            ]
        },
    )
    await facade.invoke_raw(
        session_id="edge:owner_1:supervisor:conv_abc",
        user_text="第二轮",
        agent_profile="edge_supervisor",
    )
    second_metering = next(event for event in facade.get_run_events("run_000002") if event.type == "metering")

    assert second_metering.payload["cache_prefix_changed"] is True
    assert (
        second_metering.payload["previous_prompt_prefix_hash"]
        == first_metering.payload["usage"]["prompt_prefix_hash"]
    )
