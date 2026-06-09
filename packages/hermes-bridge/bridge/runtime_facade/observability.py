from __future__ import annotations

from typing import Any

# Stable metric names for Bridge/runtime observability dashboards.
HERMES_METRIC_NAMES = {
    "hermes_run_duration_ms",
    "hermes_event_append_lag_ms",
    "hermes_sse_reconnect_total",
    "hermes_timeline_projection_lag_ms",
    "hermes_outbox_failure_total",
    "hermes_approval_wait_ms",
    "hermes_prompt_cache_hit_percent",
}


def build_structured_log(event: str, **fields: Any) -> dict[str, Any]:
    return {"event": event, **fields}
