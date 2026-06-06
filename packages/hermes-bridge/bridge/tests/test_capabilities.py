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
