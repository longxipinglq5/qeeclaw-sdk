from __future__ import annotations

import pytest


def test_capability_registry_lists_builtin_skill_apps():
    from bridge.runtime_facade.capabilities import CapabilityRegistry

    registry = CapabilityRegistry.with_builtin_capabilities()
    capabilities = registry.list_capabilities()

    assert {capability.capability_id for capability in capabilities} >= {
        "moments_copywriter",
        "xiaohongshu_note_writer",
        "moments_copywriter_with_image",
    }
    xhs = registry.get_capability("xiaohongshu_note_writer")
    assert xhs.kind == "skill_app"
    assert xhs.title == "小红书种草文"
    assert xhs.hermes_profile == "edge_supervisor"
    assert xhs.slash_command == "xhs-note-generator"
    assert xhs.output_contract == "skill_app_card"
    assert xhs.approval_policy == "preview"


def test_capability_registry_looks_up_moments_copywriter():
    from bridge.runtime_facade.capabilities import CapabilityRegistry

    capability = CapabilityRegistry.with_builtin_capabilities().get_capability(
        "moments_copywriter"
    )

    assert capability.capability_id == "moments_copywriter"
    assert capability.slash_command == "moments-copy-generator"
    assert capability.input_schema["properties"]["product"]["type"] == "string"


def test_capability_manifest_rejects_unknown_kind():
    from pydantic import ValidationError

    from bridge.runtime_facade.models import CapabilityManifest

    with pytest.raises(ValidationError):
        CapabilityManifest(
            capability_id="bad",
            kind="unknown",
            title="bad",
            description="bad",
            input_schema={},
            output_contract="bad",
            hermes_profile="edge_supervisor",
            slash_command="bad",
            permissions=[],
            approval_policy="preview",
        )


async def test_capability_api_lists_and_reads_capabilities():
    from httpx import ASGITransport, AsyncClient

    from bridge.main import create_app
    from bridge.runtime_facade.facade import HermesRuntimeFacade
    from bridge.tests.test_runtime_facade import FakeLegacyRuntime

    app = create_app()
    app.state.runtime = FakeLegacyRuntime()
    app.state.runtime_facade = HermesRuntimeFacade(app.state.runtime)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_resp = await client.get("/api/capabilities")
        detail_resp = await client.get("/api/capabilities/moments_copywriter")
        missing_resp = await client.get("/api/capabilities/missing")

    assert list_resp.status_code == 200
    assert "capabilities" in list_resp.json()
    assert {
        capability["capability_id"] for capability in list_resp.json()["capabilities"]
    } >= {"moments_copywriter", "xiaohongshu_note_writer"}
    assert detail_resp.status_code == 200
    assert detail_resp.json()["capability"]["slash_command"] == "moments-copy-generator"
    assert missing_resp.status_code == 404
    assert missing_resp.json()["error"]["code"] == "CAPABILITY_NOT_FOUND"
