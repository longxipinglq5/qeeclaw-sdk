from __future__ import annotations

import logging

from fastapi import APIRouter

from bridge.api.models import ToolsListResponse
from bridge.tools_scanner import scan_edge_skills

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/tools/list", response_model=ToolsListResponse)
async def list_tools() -> ToolsListResponse:
    tools = scan_edge_skills()
    return ToolsListResponse(tools=tools)
