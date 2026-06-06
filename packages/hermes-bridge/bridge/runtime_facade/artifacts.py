from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bridge.runtime_facade.models import RuntimeArtifact


class ArtifactConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArtifactStoreCapabilities:
    durable: bool = False
    supports_cross_worker: bool = False
    supports_pagination: bool = False


class JsonArtifactStore:
    """Local-E2E JSON artifact storage.

    This store is single-worker/local only. Move to SQLite or another durable
    store before enabling cross-worker Bridge, large artifact list pagination,
    high-concurrency writes, or durable outbox/automation replay.
    """

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.artifacts_dir = self.root_dir / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.capabilities = ArtifactStoreCapabilities()

    def create_artifact(
        self,
        *,
        artifact_id: str,
        session_id: str,
        run_id: str,
        kind: str,
        title: str,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeArtifact:
        artifact = RuntimeArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            run_id=run_id,
            kind=kind,
            title=title,
            content=content,
            metadata=metadata or {},
        )
        path = self._path_for(artifact_id)
        if path.exists():
            raise ArtifactConflictError(f"Artifact already exists: {artifact_id}")

        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            artifact.model_dump_json(indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)
        return artifact

    def get_artifact(self, artifact_id: str) -> RuntimeArtifact | None:
        path = self._path_for(artifact_id)
        if not path.exists():
            return None
        return RuntimeArtifact.model_validate_json(path.read_text(encoding="utf-8"))

    def list_for_run(self, run_id: str) -> list[RuntimeArtifact]:
        artifacts: list[RuntimeArtifact] = []
        for path in sorted(self.artifacts_dir.glob("*.json")):
            artifact = RuntimeArtifact.model_validate_json(path.read_text(encoding="utf-8"))
            if artifact.run_id == run_id:
                artifacts.append(artifact)
        return artifacts

    def garbage_collect(self, orphan_threshold_hours: int = 72) -> dict[str, Any]:
        return {"deleted": 0, "reason": "gc_deferred"}

    def _path_for(self, artifact_id: str) -> Path:
        return self.artifacts_dir / f"{artifact_id}.json"
