from __future__ import annotations

import pytest


def test_card_manifest_builders_create_timeline_ready_cards():
    from bridge.runtime_facade.cards import (
        build_approval_request_card,
        build_artifact_reference_card,
        build_error_card,
        build_result_preview_card,
    )

    result = build_result_preview_card(
        run_id="run_000001",
        title="儿童护眼台灯小红书种草文",
        summary="突出护眼、学习场景和家长安心。",
        artifact_ids=["art_xhs_001"],
    )
    artifact = build_artifact_reference_card(
        run_id="run_000001",
        artifact_id="art_xhs_001",
        title="小红书文案",
        summary="可复用的文案 artifact",
    )
    approval = build_approval_request_card(
        run_id="run_000001",
        approval_id="apr_001",
        action_kind="publish_content",
        title="发布确认",
        summary="需要确认后发布",
    )
    error = build_error_card(
        run_id="run_000001",
        title="运行失败",
        summary="provider failed",
    )

    assert result.card_type == "result_preview"
    assert result.artifact_ids == ["art_xhs_001"]
    assert artifact.card_type == "artifact_reference"
    assert approval.card_type == "approval_request"
    assert approval.approval_id == "apr_001"
    assert error.card_type == "error_card"
    assert error.fallback_text == "provider failed"


def test_card_manifest_rejects_unknown_card_type():
    from pydantic import ValidationError

    from bridge.runtime_facade.models import CardManifest

    with pytest.raises(ValidationError):
        CardManifest(
            card_id="card_001",
            card_type="unknown",
            title="bad",
            summary="bad",
            run_id="run_000001",
        )
