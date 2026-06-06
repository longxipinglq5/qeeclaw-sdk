from __future__ import annotations

from bridge.runtime_facade.models import CardManifest


def build_result_preview_card(
    *,
    run_id: str,
    title: str,
    summary: str,
    artifact_ids: list[str],
) -> CardManifest:
    return CardManifest(
        card_id=f"card_result_{run_id}",
        card_type="result_preview",
        title=title,
        summary=summary,
        artifact_ids=artifact_ids,
        run_id=run_id,
        fallback_text=summary,
    )


def build_artifact_reference_card(
    *,
    run_id: str,
    artifact_id: str,
    title: str,
    summary: str,
) -> CardManifest:
    return CardManifest(
        card_id=f"card_artifact_{artifact_id}",
        card_type="artifact_reference",
        title=title,
        summary=summary,
        artifact_ids=[artifact_id],
        run_id=run_id,
        fallback_text=summary,
    )


def build_approval_request_card(
    *,
    run_id: str,
    approval_id: str,
    action_kind: str,
    title: str,
    summary: str,
) -> CardManifest:
    return CardManifest(
        card_id=f"card_approval_{approval_id}",
        card_type="approval_request",
        title=title,
        summary=summary,
        run_id=run_id,
        approval_id=approval_id,
        action_kind=action_kind,
        status="pending",
        fallback_text=summary,
    )


def build_error_card(*, run_id: str, title: str, summary: str) -> CardManifest:
    return CardManifest(
        card_id=f"card_error_{run_id}",
        card_type="error_card",
        title=title,
        summary=summary,
        run_id=run_id,
        status="error",
        fallback_text=summary,
    )
