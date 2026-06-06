from __future__ import annotations

import pytest


def test_json_artifact_store_creates_reads_and_lists_for_run(tmp_path):
    from bridge.runtime_facade.artifacts import JsonArtifactStore

    store = JsonArtifactStore(tmp_path)
    artifact = store.create_artifact(
        artifact_id="art_xhs_001",
        session_id="edge:owner_1:supervisor:conv_abc",
        run_id="run_000001",
        kind="xiaohongshu_note",
        title="儿童护眼台灯小红书种草文",
        content={"title": "给孩子换台灯后", "body": "..."},
        metadata={"summary": "真实分享语气"},
    )

    assert artifact.artifact_id == "art_xhs_001"
    assert store.get_artifact("art_xhs_001").title == "儿童护眼台灯小红书种草文"
    assert [item.artifact_id for item in store.list_for_run("run_000001")] == [
        "art_xhs_001"
    ]
    assert store.capabilities.durable is False
    assert store.capabilities.supports_cross_worker is False
    assert store.capabilities.supports_pagination is False
    assert store.garbage_collect() == {"deleted": 0, "reason": "gc_deferred"}


def test_json_artifact_store_does_not_silently_overwrite(tmp_path):
    from bridge.runtime_facade.artifacts import ArtifactConflictError, JsonArtifactStore

    store = JsonArtifactStore(tmp_path)
    store.create_artifact(
        artifact_id="art_xhs_001",
        session_id="session_1",
        run_id="run_000001",
        kind="note",
        title="first",
        content={"body": "first"},
    )

    with pytest.raises(ArtifactConflictError):
        store.create_artifact(
            artifact_id="art_xhs_001",
            session_id="session_1",
            run_id="run_000001",
            kind="note",
            title="second",
            content={"body": "second"},
        )
