from __future__ import annotations


def test_knowledge_search_handler_is_read_only(monkeypatch):
    from bridge import knowledge_mcp_server

    calls = {}

    def fake_search_knowledge(query: str, top_k: int = 5, scope=None, **kwargs):
        calls["query"] = query
        calls["top_k"] = top_k
        calls["scope"] = scope
        return [{"text": "会员日满减活动", "score": 0.91, "filename": "campaign.md"}]

    monkeypatch.setattr(knowledge_mcp_server, "search_knowledge", fake_search_knowledge)

    result = knowledge_mcp_server.handle_knowledge_search({
        "query": "会员日活动",
        "top_k": 3,
        "scope": "team:1",
    })

    assert calls == {"query": "会员日活动", "top_k": 3, "scope": "team:1"}
    assert result["results"][0]["text"] == "会员日满减活动"
    assert "upload" not in knowledge_mcp_server.TOOL_NAMES
    assert "delete" not in knowledge_mcp_server.TOOL_NAMES
    assert "ingest" not in knowledge_mcp_server.TOOL_NAMES


def test_knowledge_stats_handler(monkeypatch):
    from bridge import knowledge_mcp_server

    monkeypatch.setattr(
        knowledge_mcp_server,
        "get_kb_stats",
        lambda: {"document_count": 2, "chunk_count": 9, "available": True},
    )

    assert knowledge_mcp_server.handle_knowledge_stats({}) == {
        "document_count": 2,
        "chunk_count": 9,
        "available": True,
    }
