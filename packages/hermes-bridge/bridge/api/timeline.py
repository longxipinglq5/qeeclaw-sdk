from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from bridge.api.errors import api_error

router = APIRouter()


def _facade(request: Request):
    return request.app.state.runtime_facade


@router.get("/api/sessions/{session_id}/timeline")
async def get_session_timeline(
    session_id: str,
    request: Request,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    after: str | None = None,
    before: str | None = None,
) -> JSONResponse:
    effective_cursor = cursor or request.headers.get("Last-Event-ID")
    page = _facade(request).timeline.list_session(
        session_id,
        cursor=effective_cursor,
        limit=limit,
    )
    return JSONResponse(page.model_dump(mode="json"))


@router.get("/api/sessions/{session_id}/timeline/stream", response_model=None)
async def stream_session_timeline(session_id: str, request: Request):
    async def _generator():
        yield ": keep-alive\n\n"

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/api/sessions/{session_id}/timeline/read-receipts")
async def update_timeline_read_receipts(session_id: str, request: Request) -> JSONResponse:
    body = await _json_or_empty(request)
    reader_id = str(body.get("reader_id") or "")
    if not _reader_matches_session(session_id, reader_id):
        return api_error(
            "TIMELINE_READER_MISMATCH",
            "reader_id does not match timeline session owner",
            400,
            {"session_id": session_id, "reader_id": reader_id},
        )
    read_at = str(body.get("read_at") or datetime.now(timezone.utc).isoformat())
    event_ids = body.get("event_ids")
    marked = _facade(request).timeline.mark_read(
        session_id=session_id,
        reader_id=reader_id,
        read_at=read_at,
        event_ids=list(event_ids) if isinstance(event_ids, list) else None,
        cursor=str(body["cursor"]) if body.get("cursor") else None,
    )
    return JSONResponse(
        {
            "events": [event.model_dump(mode="json") for event in marked],
        }
    )


async def _json_or_empty(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _reader_matches_session(session_id: str, reader_id: str) -> bool:
    parts = session_id.split(":")
    return len(parts) >= 2 and parts[0] == "edge" and parts[1] == reader_id
