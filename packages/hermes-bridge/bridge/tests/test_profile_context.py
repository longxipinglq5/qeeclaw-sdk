from __future__ import annotations

import pytest

from bridge.profile_context import (
    ProfileContext,
    build_profile_context_prompt,
    save_profile_context,
)
from bridge.scenarios import get_system_prompt


class TestProfileContext:
    def test_profile_context_is_added_to_system_prompt(self, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))

        save_profile_context(
            ProfileContext(
                agent_profile="edge_supervisor",
                owner_context="主人姓名/昵称：林总",
                business_context="企业名称：星图律所",
                source="edge",
                updated_at="2026-06-04T00:00:00Z",
            )
        )

        context_prompt = build_profile_context_prompt("edge_supervisor")
        assert "主人姓名/昵称：林总" in context_prompt
        assert "企业名称：星图律所" in context_prompt

        system_prompt = get_system_prompt("supervisor", agent_profile="edge_supervisor")
        assert "已同步的用户与企业资料" in system_prompt
        assert "主人姓名/昵称：林总" in system_prompt
        assert "企业名称：星图律所" in system_prompt

    @pytest.mark.asyncio
    async def test_sync_endpoint_persists_context_and_evicts_agent(self, app_client, fresh_runtime, tmp_path, monkeypatch):
        from bridge import config

        monkeypatch.setattr(config.settings, "hermes_home", str(tmp_path))
        fresh_runtime._cache["compat:edge:supervisor:edge_supervisor"] = object()

        resp = await app_client.post(
            "/profile-context/sync",
            json={
                "agent_profile": "edge_supervisor",
                "owner_context": "AI 对主人的固定称呼：老板",
                "business_context": "主营业务：常年法律顾问",
                "source": "edge-open",
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["evicted_agents"] == 1
        assert fresh_runtime.cache_size == 0

        system_prompt = get_system_prompt("supervisor", agent_profile="edge_supervisor")
        assert "AI 对主人的固定称呼：老板" in system_prompt
        assert "主营业务：常年法律顾问" in system_prompt
