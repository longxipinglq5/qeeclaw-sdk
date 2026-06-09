from __future__ import annotations

import json
import sys
from typing import Any

from knowledge_store import get_document, get_kb_stats, search_knowledge

TOOL_NAMES = {
    "knowledge.search",
    "knowledge.stats",
    "knowledge.getDocument",
}


def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def handle_knowledge_search(arguments: dict[str, Any]) -> dict[str, Any]:
    query = str(arguments.get("query") or "").strip()
    top_k = _as_int(arguments.get("top_k", arguments.get("limit", 5)), 5, 1, 10)
    raw_scope = arguments.get("scope")
    scope = str(raw_scope).strip() if raw_scope is not None else None
    if not query:
        return {"results": [], "error": "query is required"}
    results = search_knowledge(query=query, top_k=top_k, scope=scope)
    return {"results": results}


def handle_knowledge_stats(arguments: dict[str, Any]) -> dict[str, Any]:
    return get_kb_stats()


def handle_knowledge_get_document(arguments: dict[str, Any]) -> dict[str, Any] | None:
    doc_id = str(arguments.get("doc_id") or arguments.get("docId") or "").strip()
    if not doc_id:
        return {"error": "doc_id is required"}
    return get_document(doc_id)


def _tool_schema() -> list[dict[str, Any]]:
    return [
        {
            "name": "knowledge.search",
            "description": "Search the local Centaur Edge knowledge base. Read-only.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
                    "scope": {"type": "string"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "knowledge.stats",
            "description": "Return local knowledge base stats. Read-only.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "knowledge.getDocument",
            "description": "Return one knowledge document by id. Read-only.",
            "inputSchema": {
                "type": "object",
                "properties": {"doc_id": {"type": "string"}},
                "required": ["doc_id"],
            },
        },
    ]


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:
        sys.stderr.write(f"mcp package is required for knowledge MCP: {exc}\n")
        raise SystemExit(2)

    app = FastMCP("centaur_knowledge")

    @app.tool(name="knowledge.search")
    def _search(query: str, top_k: int = 5, scope: str | None = None) -> str:
        return json.dumps(
            handle_knowledge_search({"query": query, "top_k": top_k, "scope": scope}),
            ensure_ascii=False,
        )

    @app.tool(name="knowledge.stats")
    def _stats() -> str:
        return json.dumps(handle_knowledge_stats({}), ensure_ascii=False)

    @app.tool(name="knowledge.getDocument")
    def _get_document(doc_id: str) -> str:
        return json.dumps(handle_knowledge_get_document({"doc_id": doc_id}), ensure_ascii=False)

    app.run()


if __name__ == "__main__":
    main()
