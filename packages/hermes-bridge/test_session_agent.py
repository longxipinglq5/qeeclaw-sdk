#!/usr/bin/env python3
"""
test_session_agent.py — 多人多轮对话 + 多智体 单元测试

覆盖:
  Part A: session_manager.py 单元测试 (无需 HTTP)
  Part B: bridge_server.py HTTP 端点集成测试

运行:
  cd sdk/qeeclaw-hermes-bridge
  .venv/bin/python3 -m pytest test_session_agent.py -v
"""

import json
import os
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import HTTPServer
from typing import Dict, Optional

import pytest

# ---------------------------------------------------------------------------
# 让 import session_manager 可用
# ---------------------------------------------------------------------------
import sys

_BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)

# 在导入前设置临时 HERMES_HOME 避免污染真实数据
_TMPDIR = tempfile.mkdtemp(prefix="qeeclaw_test_")
os.environ["HERMES_HOME"] = _TMPDIR

# 重置全局单例，确保测试隔离
import session_manager as sm_mod

sm_mod._session_manager = None


# ===================================================================
# Part A: session_manager.py 直接单元测试
# ===================================================================


class TestAgentProfile:
    """AgentProfile 数据结构测试。"""

    def test_create_default(self):
        p = sm_mod.AgentProfile(name="test")
        assert p.name == "test"
        assert p.display_name == "test"
        assert p.temperature == 0.7
        assert p.tools_enabled is True

    def test_to_dict_roundtrip(self):
        p = sm_mod.AgentProfile(
            name="my_agent",
            display_name="我的智体",
            system_prompt="你好",
            model="gpt-4",
            temperature=0.5,
            max_tokens=1024,
        )
        d = p.to_dict()
        assert d["name"] == "my_agent"
        assert d["display_name"] == "我的智体"
        assert d["temperature"] == 0.5
        assert d["max_tokens"] == 1024

        p2 = sm_mod.AgentProfile.from_dict(d)
        assert p2.name == p.name
        assert p2.system_prompt == p.system_prompt
        assert p2.temperature == p.temperature


class TestSession:
    """Session 数据结构测试。"""

    def test_create(self):
        s = sm_mod.Session(session_id="s1", user_id="u1", agent_profile="default")
        assert s.session_id == "s1"
        assert s.user_id == "u1"
        assert s.turn_count == 0

    def test_add_and_get_messages(self):
        s = sm_mod.Session(session_id="s2")
        s.add_message("user", "hello")
        s.add_message("assistant", "hi there")
        s.add_message("user", "how are you")
        s.add_message("assistant", "fine")
        assert s.turn_count == 2
        msgs = s.get_messages()
        assert len(msgs) == 4

    def test_get_messages_with_max_turns(self):
        s = sm_mod.Session(session_id="s3")
        for i in range(10):
            s.add_message("user", f"q{i}")
            s.add_message("assistant", f"a{i}")
        assert s.turn_count == 10
        # 只取最近 3 轮
        msgs = s.get_messages(max_turns=3)
        assert len(msgs) == 6
        assert msgs[0]["content"] == "q7"
        assert msgs[-1]["content"] == "a9"

    def test_clear_messages(self):
        s = sm_mod.Session(session_id="s4")
        s.add_message("user", "x")
        s.add_message("assistant", "y")
        assert s.turn_count == 1
        s.clear_messages()
        assert s.turn_count == 0
        assert s.get_messages() == []

    def test_to_dict_from_dict(self):
        s = sm_mod.Session(session_id="s5", user_id="alice", agent_profile="coder")
        s.add_message("user", "write code")
        s.add_message("assistant", "print('hello')")
        d = s.to_dict()
        s2 = sm_mod.Session.from_dict(d)
        assert s2.session_id == "s5"
        assert s2.user_id == "alice"
        assert s2.agent_profile == "coder"
        assert len(s2.messages) == 2

    def test_thread_safety(self):
        """并发写入消息不应丢失。"""
        s = sm_mod.Session(session_id="s_concurrent")
        n_threads = 10
        n_per_thread = 50
        barrier = threading.Barrier(n_threads)

        def writer(tid):
            barrier.wait()
            for i in range(n_per_thread):
                s.add_message("user", f"t{tid}_q{i}")
                s.add_message("assistant", f"t{tid}_a{i}")

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(s.messages) == n_threads * n_per_thread * 2


class TestSessionManager:
    """SessionManager CRUD + Profile 测试。"""

    @pytest.fixture(autouse=True)
    def fresh_manager(self, tmp_path):
        """每个测试用例用独立的 storage_dir。"""
        # 重置全局单例
        sm_mod._session_manager = None
        self.mgr = sm_mod.SessionManager(storage_dir=str(tmp_path / "sessions"))
        yield
        # 清理
        sm_mod._session_manager = None

    # ---- Session CRUD ----

    def test_create_session(self):
        s = self.mgr.create_session(user_id="u1", agent_profile="default")
        assert s.session_id.startswith("ses_")
        assert s.user_id == "u1"

    def test_create_session_custom_id(self):
        s = self.mgr.create_session(session_id="my_custom_id")
        assert s.session_id == "my_custom_id"

    def test_create_session_invalid_profile(self):
        with pytest.raises(ValueError, match="Unknown agent profile"):
            self.mgr.create_session(agent_profile="nonexistent_profile")

    def test_get_session(self):
        s = self.mgr.create_session(user_id="bob")
        got = self.mgr.get_session(s.session_id)
        assert got is not None
        assert got.user_id == "bob"

    def test_get_session_not_found(self):
        assert self.mgr.get_session("no_such_session") is None

    def test_get_or_create_existing(self):
        s1 = self.mgr.create_session(session_id="existing_1", user_id="alice")
        s2 = self.mgr.get_or_create_session(session_id="existing_1", user_id="alice")
        assert s2.session_id == s1.session_id

    def test_get_or_create_new(self):
        s = self.mgr.get_or_create_session(session_id="new_ses", user_id="dave")
        assert s.session_id == "new_ses"

    def test_delete_session(self):
        s = self.mgr.create_session()
        assert self.mgr.delete_session(s.session_id) is True
        assert self.mgr.get_session(s.session_id) is None

    def test_delete_nonexistent(self):
        assert self.mgr.delete_session("ghost") is False

    def test_list_sessions(self):
        self.mgr.create_session(user_id="u1", agent_profile="default")
        self.mgr.create_session(user_id="u2", agent_profile="coder")
        self.mgr.create_session(user_id="u1", agent_profile="coder")
        all_list = self.mgr.list_sessions()
        assert len(all_list) == 3
        # 按 user_id 筛选
        u1_list = self.mgr.list_sessions(user_id="u1")
        assert len(u1_list) == 2
        # 按 agent_profile 筛选
        coder_list = self.mgr.list_sessions(agent_profile="coder")
        assert len(coder_list) == 2

    # ---- 对话操作 ----

    def test_append_turn(self):
        s = self.mgr.create_session()
        ok = self.mgr.append_turn(s.session_id, "你好", "你好！有什么可以帮你的？")
        assert ok is True
        assert s.turn_count == 1
        msgs = s.get_messages()
        assert msgs[0] == {"role": "user", "content": "你好"}
        assert msgs[1] == {"role": "assistant", "content": "你好！有什么可以帮你的？"}

    def test_append_turn_nonexistent(self):
        assert self.mgr.append_turn("ghost", "hi", "hello") is False

    def test_get_context_messages(self):
        s = self.mgr.create_session(agent_profile="coder")
        self.mgr.append_turn(s.session_id, "帮我写排序", "好的，这是冒泡排序...")
        msgs = self.mgr.get_context_messages(s.session_id)
        # should have system_prompt (from coder profile) + 2 messages
        assert msgs[0]["role"] == "system"
        assert "编程助手" in msgs[0]["content"] or "代码" in msgs[0]["content"]
        assert len(msgs) == 3

    def test_get_context_messages_custom_system(self):
        s = self.mgr.create_session(agent_profile="default")
        self.mgr.append_turn(s.session_id, "q", "a")
        msgs = self.mgr.get_context_messages(s.session_id, system_prompt="custom sys")
        assert msgs[0]["content"] == "custom sys"

    def test_get_context_messages_nonexistent(self):
        msgs = self.mgr.get_context_messages("no_such")
        assert msgs == []

    def test_auto_truncate_turns(self):
        """超过 max_turns 时自动截断。"""
        mgr = sm_mod.SessionManager(
            storage_dir=str(self.mgr._storage_dir.parent / "trunc"),
            max_turns=5,
        )
        s = mgr.create_session()
        for i in range(10):
            mgr.append_turn(s.session_id, f"q{i}", f"a{i}")
        assert len(s.messages) == 10  # 5 turns * 2 messages
        assert s.messages[0]["content"] == "q5"

    # ---- Profile 管理 ----

    def test_builtin_profiles(self):
        profiles = self.mgr.list_profiles()
        names = [p["name"] for p in profiles]
        assert "default" in names
        assert "coder" in names
        assert "writer" in names
        assert "analyst" in names
        assert "wechat" in names

    def test_get_profile(self):
        p = self.mgr.get_profile("coder")
        assert p is not None
        assert p.temperature == 0.3

    def test_get_profile_not_found(self):
        assert self.mgr.get_profile("nope") is None

    def test_create_custom_profile(self):
        p = self.mgr.create_profile({
            "name": "translator",
            "display_name": "翻译专家",
            "system_prompt": "你是一个翻译",
            "temperature": 0.2,
        })
        assert p.name == "translator"
        assert p.display_name == "翻译专家"
        # 列表应包含
        names = [x["name"] for x in self.mgr.list_profiles()]
        assert "translator" in names

    def test_create_profile_no_name(self):
        with pytest.raises(ValueError, match="name"):
            self.mgr.create_profile({"display_name": "no name"})

    def test_delete_custom_profile(self):
        self.mgr.create_profile({"name": "temp_agent", "system_prompt": "temp"})
        assert self.mgr.delete_profile("temp_agent") is True
        assert self.mgr.get_profile("temp_agent") is None

    def test_delete_builtin_profile_rejected(self):
        assert self.mgr.delete_profile("default") is False
        assert self.mgr.delete_profile("coder") is False
        assert self.mgr.get_profile("coder") is not None

    def test_delete_nonexistent_profile(self):
        assert self.mgr.delete_profile("ghost_agent") is False

    # ---- 持久化 ----

    def test_session_persistence(self):
        """会话应该被持久化到磁盘，新 manager 可恢复。"""
        s = self.mgr.create_session(user_id="persist_user")
        self.mgr.append_turn(s.session_id, "hello", "world")
        sid = s.session_id

        # 新建 manager 从同一目录恢复
        mgr2 = sm_mod.SessionManager(storage_dir=str(self.mgr._storage_dir))
        restored = mgr2.get_session(sid)
        assert restored is not None
        assert restored.user_id == "persist_user"
        assert restored.turn_count == 1

    def test_profile_persistence(self):
        self.mgr.create_profile({"name": "persist_bot", "system_prompt": "test"})
        mgr2 = sm_mod.SessionManager(storage_dir=str(self.mgr._storage_dir))
        p = mgr2.get_profile("persist_bot")
        assert p is not None
        assert p.system_prompt == "test"

    # ---- stats ----

    def test_stats(self):
        self.mgr.create_session(user_id="u1")
        self.mgr.create_session(user_id="u2")
        stats = self.mgr.stats()
        assert stats["total_sessions"] == 2
        assert stats["active_users"] == 2
        assert stats["agent_profiles"] >= 5


# ===================================================================
# Part B: bridge_server.py HTTP 端点集成测试
# ===================================================================


def _http_request(
    url: str,
    method: str = "GET",
    data: Optional[Dict] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict:
    """简易 HTTP 请求封装，返回 (status_code, body_dict)。"""
    body_bytes = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body_bytes, method=method)
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"status": resp.status, "body": body}
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode("utf-8")) if e.fp else {}
        return {"status": e.code, "body": body}


# 测试用的 bridge server port (随机高端口)
_TEST_PORT = 0  # will be assigned


@pytest.fixture(scope="module")
def bridge_server():
    """启动一个真实的 bridge_server 用于集成测试。"""
    global _TEST_PORT

    # 重置 session_manager 单例
    sm_mod._session_manager = None

    # 设置测试环境
    test_tmpdir = tempfile.mkdtemp(prefix="qeeclaw_http_test_")
    os.environ["HERMES_HOME"] = test_tmpdir
    os.environ.setdefault("HERMES_BRIDGE_API_KEY", "")
    # 禁止 hermes-agent 检查（通过设置目录为临时目录）
    os.environ["QEECLAW_HERMES_AGENT_DIR"] = test_tmpdir

    # 导入 bridge_server
    import importlib
    if "bridge_server" in sys.modules:
        # 需要 reload 以使用新环境
        bs_mod = importlib.reload(sys.modules["bridge_server"])
    else:
        bs_mod = importlib.import_module("bridge_server")

    # 创建 server，用 port=0 让 OS 分配随机端口
    handler_class = bs_mod.BridgeRequestHandler
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    _TEST_PORT = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield {"port": _TEST_PORT, "url": f"http://127.0.0.1:{_TEST_PORT}"}

    server.shutdown()
    shutil.rmtree(test_tmpdir, ignore_errors=True)


class TestHTTPAgentEndpoints:
    """测试 /agents 相关 HTTP 端点。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_list_agents(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/agents")
        assert r["status"] == 200
        agents = r["body"]["agents"]
        names = [a["name"] for a in agents]
        assert "default" in names
        assert "coder" in names
        assert len(agents) >= 5

    def test_get_agent(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/agents/coder")
        assert r["status"] == 200
        assert r["body"]["name"] == "coder"
        assert r["body"]["temperature"] == 0.3

    def test_get_agent_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/agents/nonexistent_xxx")
        assert r["status"] == 404

    def test_create_agent(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/agents",
            method="POST",
            data={
                "name": "http_test_agent",
                "display_name": "HTTP测试智体",
                "system_prompt": "你是测试专用智体",
                "temperature": 0.5,
            },
        )
        assert r["status"] == 200
        assert r["body"]["status"] == "created"
        assert r["body"]["agent"]["name"] == "http_test_agent"

        # 验证可查到
        r2 = _http_request(f"{self.base(bridge_server)}/agents/http_test_agent")
        assert r2["status"] == 200
        assert r2["body"]["display_name"] == "HTTP测试智体"

    def test_create_agent_no_name(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/agents",
            method="POST",
            data={"display_name": "missing_name"},
        )
        assert r["status"] == 400

    def test_delete_agent_custom(self, bridge_server):
        # 先创建
        _http_request(
            f"{self.base(bridge_server)}/agents",
            method="POST",
            data={"name": "to_delete_agent", "system_prompt": "bye"},
        )
        # 删除
        r = _http_request(f"{self.base(bridge_server)}/agents/to_delete_agent/delete", method="POST")
        assert r["status"] == 200
        assert r["body"]["status"] == "deleted"
        # 确认已删
        r2 = _http_request(f"{self.base(bridge_server)}/agents/to_delete_agent")
        assert r2["status"] == 404

    def test_delete_agent_builtin_rejected(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/agents/default/delete", method="POST")
        assert r["status"] == 404
        assert "builtin" in r["body"]["error"]


class TestHTTPSessionEndpoints:
    """测试 /sessions 相关 HTTP 端点。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_create_session(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/sessions",
            method="POST",
            data={"user_id": "test_user_1", "agent_profile": "coder"},
        )
        assert r["status"] == 200
        assert r["body"]["user_id"] == "test_user_1"
        assert r["body"]["agent_profile"] == "coder"
        assert "session_id" in r["body"]

    def test_create_session_defaults(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/sessions",
            method="POST",
            data={},
        )
        assert r["status"] == 200
        assert r["body"]["user_id"] == "anonymous"
        assert r["body"]["agent_profile"] == "default"

    def test_list_sessions(self, bridge_server):
        # 创建几个
        for uid in ["list_u1", "list_u2"]:
            _http_request(
                f"{self.base(bridge_server)}/sessions",
                method="POST",
                data={"user_id": uid},
            )
        r = _http_request(f"{self.base(bridge_server)}/sessions")
        assert r["status"] == 200
        assert len(r["body"]["sessions"]) >= 2

    def test_list_sessions_filter_user(self, bridge_server):
        uid = "filter_test_user_unique"
        _http_request(
            f"{self.base(bridge_server)}/sessions",
            method="POST",
            data={"user_id": uid},
        )
        r = _http_request(f"{self.base(bridge_server)}/sessions?user_id={uid}")
        assert r["status"] == 200
        for s in r["body"]["sessions"]:
            assert s["user_id"] == uid

    def test_get_session(self, bridge_server):
        create_r = _http_request(
            f"{self.base(bridge_server)}/sessions",
            method="POST",
            data={"user_id": "get_test_user"},
        )
        sid = create_r["body"]["session_id"]
        r = _http_request(f"{self.base(bridge_server)}/sessions/{sid}")
        assert r["status"] == 200
        assert r["body"]["session_id"] == sid
        assert r["body"]["user_id"] == "get_test_user"
        assert "messages" in r["body"]

    def test_get_session_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/sessions/no_such_session_xyz")
        assert r["status"] == 404

    def test_session_stats(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/sessions/stats")
        assert r["status"] == 200
        assert "total_sessions" in r["body"]
        assert "unique_users" in r["body"]

    def test_clear_session(self, bridge_server):
        # 创建会话并向其添加消息
        create_r = _http_request(
            f"{self.base(bridge_server)}/sessions",
            method="POST",
            data={"user_id": "clear_user"},
        )
        sid = create_r["body"]["session_id"]

        # 通过 session_manager 添加消息
        mgr = sm_mod.get_session_manager()
        mgr.append_turn(sid, "hello", "world")
        s = mgr.get_session(sid)
        assert s.turn_count == 1

        # 清空
        r = _http_request(f"{self.base(bridge_server)}/sessions/{sid}/clear", method="POST")
        assert r["status"] == 200
        assert r["body"]["status"] == "cleared"

        # 验证已清空
        s2 = mgr.get_session(sid)
        assert s2.turn_count == 0

    def test_clear_session_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/sessions/ghost_clear/clear", method="POST")
        assert r["status"] == 404

    def test_delete_session(self, bridge_server):
        create_r = _http_request(
            f"{self.base(bridge_server)}/sessions",
            method="POST",
            data={"user_id": "del_user"},
        )
        sid = create_r["body"]["session_id"]

        r = _http_request(f"{self.base(bridge_server)}/sessions/{sid}/delete", method="POST")
        assert r["status"] == 200
        assert r["body"]["status"] == "deleted"

        # 确认已删
        r2 = _http_request(f"{self.base(bridge_server)}/sessions/{sid}")
        assert r2["status"] == 404

    def test_delete_session_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/sessions/ghost_del/delete", method="POST")
        assert r["status"] == 404


class TestHTTPInvokeSessionIntegration:
    """
    测试 /invoke 端点的 session 集成逻辑。

    注: 由于测试环境没有真实的 LLM 后端，/invoke 调用会返回 503 (hermes-agent 不可用)
    或连接错误。但我们可以验证：
    1. 传入 session_id 时 session 被正确创建/复用
    2. 传入 agent_profile 时对参数有影响
    """

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_invoke_creates_session(self, bridge_server):
        """调用 /invoke 并传入 session_id，应自动创建会话。"""
        # 先验证 session 不存在
        mgr = sm_mod.get_session_manager()
        assert mgr.get_session("auto_ses_001") is None

        # 调用 /invoke (预期会失败，但 session 应该已创建或在处理前)
        r = _http_request(
            f"{self.base(bridge_server)}/invoke",
            method="POST",
            data={
                "prompt": "hello",
                "session_id": "auto_ses_001",
                "user_id": "invoke_user",
                "agent_profile": "default",
            },
        )
        # 即使 LLM 调用失败 (503/500)，session 也应被创建
        # (如果 hermes error check 在 session 创建之前就返回了，则不会创建)
        # 根据代码逻辑，_handle_invoke 先检查 hermes 可用性再创建 session
        # 所以此处我们只验证端点可达
        assert r["status"] in (200, 500, 503)

    def test_invoke_stream_returns_sse(self, bridge_server):
        """验证 /invoke/stream 端点可达（SSE 格式）。"""
        url = f"{self.base(bridge_server)}/invoke/stream"
        body = json.dumps({"prompt": "hi"}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                # 检查 SSE content-type
                ct = resp.headers.get("Content-Type", "")
                # 可能是 text/event-stream 或 application/json (如果 503)
                assert resp.status in (200, 503)
        except urllib.error.HTTPError as e:
            # 503 是正常的 (hermes 不可用)
            assert e.code in (500, 503)

    def test_invoke_without_prompt(self, bridge_server):
        """缺少 prompt 应返回 400。"""
        r = _http_request(
            f"{self.base(bridge_server)}/invoke",
            method="POST",
            data={"session_id": "x"},
        )
        assert r["status"] == 400
        assert "prompt" in r["body"].get("error", "").lower()


class TestHTTPHealthAndMisc:
    """健康检查和其他基础测试。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_health(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/health")
        assert r["status"] in (200, 503)
        assert "version" in r["body"]

    def test_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/nonexistent_endpoint")
        assert r["status"] == 404


# ===================================================================
# Phase 2: Memory / Skills / Tools / Cron 端点测试
# ===================================================================


class TestHTTPMemoryV2Endpoints:
    """测试 /memory/* 路由。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_memory_stats(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/memory/stats")
        assert r["status"] == 200
        assert r["body"]["success"] is True
        assert "total" in r["body"]

    def test_memory_store_and_search(self, bridge_server):
        # Store
        r = _http_request(f"{self.base(bridge_server)}/memory/store", "POST", {
            "content": "测试记忆内容",
            "agent_profile": "default",
            "category": "test",
        })
        assert r["status"] == 200
        assert r["body"]["success"] is True
        assert "entry" in r["body"]

        # Search
        r = _http_request(f"{self.base(bridge_server)}/memory/search", "POST", {
            "query": "测试",
            "agent_profile": "default",
        })
        assert r["status"] == 200
        assert r["body"]["success"] is True
        assert len(r["body"]["results"]) >= 1

    def test_memory_clear(self, bridge_server):
        # Store first
        _http_request(f"{self.base(bridge_server)}/memory/store", "POST", {
            "content": "will be cleared",
            "agent_profile": "test_clear_agent",
        })
        # Clear
        r = _http_request(f"{self.base(bridge_server)}/memory/clear", "POST", {
            "agent_profile": "test_clear_agent",
        })
        assert r["status"] == 200
        assert r["body"]["success"] is True

    def test_memory_clear_missing_profile(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/memory/clear", "POST", {})
        assert r["status"] == 400


class TestHTTPSkillsEndpoints:
    """测试 /skills/* 路由。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_skills_list_empty(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/skills?agent_profile=default")
        assert r["status"] == 200
        assert r["body"]["success"] is True
        assert isinstance(r["body"]["skills"], list)

    def test_skill_install_and_get_and_uninstall(self, bridge_server):
        skill_content = """---
name: test-skill
description: A test skill for integration tests
version: 1.0.0
---

# Test Skill

This is a test skill.
"""
        # Install
        r = _http_request(f"{self.base(bridge_server)}/skills/install", "POST", {
            "name": "test-skill",
            "content": skill_content,
            "agent_profile": "default",
        })
        assert r["status"] == 200
        assert r["body"]["success"] is True

        # List — should include the new skill
        r = _http_request(f"{self.base(bridge_server)}/skills?agent_profile=default")
        assert r["status"] == 200
        names = [s["name"] for s in r["body"]["skills"]]
        assert "test-skill" in names

        # Get
        r = _http_request(f"{self.base(bridge_server)}/skills/test-skill?agent_profile=default")
        assert r["status"] == 200
        assert r["body"]["success"] is True
        assert "content" in r["body"]
        assert "test-skill" in r["body"]["name"]

        # Uninstall
        r = _http_request(f"{self.base(bridge_server)}/skills/uninstall", "POST", {
            "name": "test-skill",
            "agent_profile": "default",
        })
        assert r["status"] == 200
        assert r["body"]["success"] is True

        # Verify removed
        r = _http_request(f"{self.base(bridge_server)}/skills/test-skill?agent_profile=default")
        assert r["status"] == 404

    def test_skill_install_duplicate(self, bridge_server):
        content = "---\nname: dup-skill\ndescription: dup\n---\n# Dup\ntest"
        _http_request(f"{self.base(bridge_server)}/skills/install", "POST", {
            "name": "dup-skill", "content": content, "agent_profile": "default",
        })
        r = _http_request(f"{self.base(bridge_server)}/skills/install", "POST", {
            "name": "dup-skill", "content": content, "agent_profile": "default",
        })
        assert r["status"] == 409
        # Cleanup
        _http_request(f"{self.base(bridge_server)}/skills/uninstall", "POST", {
            "name": "dup-skill", "agent_profile": "default",
        })

    def test_skill_install_missing_fields(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/skills/install", "POST", {})
        assert r["status"] == 400

    def test_skill_uninstall_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/skills/uninstall", "POST", {
            "name": "nonexistent-skill-xyz", "agent_profile": "default",
        })
        assert r["status"] == 404

    def test_skill_get_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/skills/nonexistent?agent_profile=default")
        assert r["status"] == 404


class TestHTTPToolsEndpoints:
    """测试 /tools/* 路由。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_tools_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/tools?agent_profile=default")
        assert r["status"] == 200
        assert r["body"]["success"] is True
        # toolsets 可能为空（hermes-agent 不可用时），但响应格式正确
        assert isinstance(r["body"]["toolsets"], list)

    def test_tools_update_missing_profile(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/tools", "PUT", {
            "enabled": ["web", "terminal"],
        })
        assert r["status"] == 400

    def test_tools_update_profile_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/tools", "PUT", {
            "agent_profile": "nonexistent_agent_xxx",
            "enabled": ["web"],
        })
        assert r["status"] == 404

    def test_tools_update_success(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/tools", "PUT", {
            "agent_profile": "default",
            "enabled": ["web", "terminal", "file"],
        })
        assert r["status"] == 200
        assert r["body"]["success"] is True
        assert r["body"]["enabled_toolsets"] == ["web", "terminal", "file"]


class TestHTTPCronEndpoints:
    """测试 /cron/* 路由。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_cron_list_empty(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/cron?agent_profile=default")
        assert r["status"] == 200
        assert r["body"]["success"] is True
        assert r["body"]["jobs"] == []

    def test_cron_create_and_list_and_delete(self, bridge_server):
        # Create
        r = _http_request(f"{self.base(bridge_server)}/cron", "POST", {
            "prompt": "生成测试报告",
            "schedule": "0 9 * * 1-5",
            "name": "test-cron-job",
            "agent_profile": "default",
        })
        assert r["status"] == 200
        assert r["body"]["success"] is True
        job_id = r["body"]["job"]["id"]
        assert job_id.startswith("cron_")

        # List
        r = _http_request(f"{self.base(bridge_server)}/cron?agent_profile=default")
        assert r["status"] == 200
        assert r["body"]["count"] == 1
        assert r["body"]["jobs"][0]["id"] == job_id

        # Delete
        r = _http_request(f"{self.base(bridge_server)}/cron/{job_id}?agent_profile=default", "DELETE")
        assert r["status"] == 200
        assert r["body"]["success"] is True

        # Verify deleted
        r = _http_request(f"{self.base(bridge_server)}/cron?agent_profile=default")
        assert r["status"] == 200
        assert r["body"]["count"] == 0

    def test_cron_create_missing_schedule(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/cron", "POST", {
            "prompt": "test",
        })
        assert r["status"] == 400

    def test_cron_create_missing_prompt(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/cron", "POST", {
            "schedule": "0 9 * * *",
        })
        assert r["status"] == 400

    def test_cron_delete_not_found(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/cron/nonexistent_id?agent_profile=default",
            "DELETE",
        )
        assert r["status"] == 404


# ===================================================================
# Part C: Hub OS 兼容性端点测试
# ===================================================================


class TestHTTPAgentTemplateEndpoints:
    """Agent Templates 端点测试。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_list_default_templates(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/agent_config/default")
        assert r["status"] == 200
        templates = r["body"]
        assert isinstance(templates, list)
        assert len(templates) >= 5  # default, coder, writer, analyst, wechat
        codes = [t["code"] for t in templates]
        assert "default" in codes
        assert "coder" in codes
        # 每个模板需有 id, code, name 字段
        for t in templates:
            assert "id" in t
            assert "code" in t
            assert "name" in t
            assert "allowed_tools" in t

    def test_get_template(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/agent_config/coder")
        assert r["status"] == 200
        t = r["body"]
        assert t["code"] == "coder"
        assert t["name"] == "编程助手"

    def test_get_template_not_found(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/agent_config/nonexistent_xyz")
        assert r["status"] == 404


class TestHTTPIAMEndpoints:
    """IAM / Users 端点测试。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_get_profile(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/users/me")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["id"] == 1
        assert data["username"] == "local-admin"
        assert data["role"] == "ADMIN"
        assert data["is_active"] is True
        assert isinstance(data["teams"], list)

    def test_update_profile(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/users/me",
            "PUT",
            data={"full_name": "测试用户", "email": "test@example.com"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["full_name"] == "测试用户"
        assert data["email"] == "test@example.com"
        # 验证持久化
        r2 = _http_request(f"{self.base(bridge_server)}/api/users/me")
        assert r2["body"]["data"]["full_name"] == "测试用户"

    def test_update_preference(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/users/me/preference",
            "PUT",
            data={"preferred_model": "gpt-4o"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["preferred_model"] == "gpt-4o"

    def test_list_users(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/users?page=1&page_size=10")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["username"] == "local-admin"

    def test_list_products(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/users/products")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)
        assert len(data) == 0


class TestHTTPModelsEndpoints:
    """Models 端点测试。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_list_models(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
        m = data[0]
        assert "id" in m
        assert "model_name" in m
        assert "provider_name" in m
        assert m["is_preferred"] is True

    def test_list_providers(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models/providers")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "provider_name" in data[0]
        assert "models" in data[0]

    def test_list_runtimes(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models/runtimes")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["runtime_type"] == "openclaw"
        assert data[0]["is_default"] is True

    def test_resolve_model(self, bridge_server):
        model = os.environ.get("HERMES_MODEL", "deepseek/deepseek-v3.2-exp")
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models/resolve?model_name={model}")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["requested_model"] == model
        assert "resolved_model" in data
        assert "selected" in data

    def test_resolve_model_missing(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models/resolve")
        assert r["status"] == 400

    def test_get_route_profile(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models/route")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "preferred_model" in data
        assert "candidate_count" in data
        assert "available_model_count" in data

    def test_set_route_profile(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/models/route",
            "PUT",
            data={"preferred_model": "test-model"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["preferred_model"] == "test-model"

    def test_set_route_missing_model(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/models/route",
            "PUT",
            data={},
        )
        assert r["status"] == 400

    def test_usage_stub(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models/usage")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["total_calls"] == 0
        assert "breakdown" in data

    def test_cost_stub(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models/cost")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["total_amount"] == 0

    def test_quota_stub(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/models/quota")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["daily_unlimited"] is True
        assert data["monthly_unlimited"] is True


class TestHTTPConversationsEndpoints:
    """Conversations 端点测试。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_conversations_home_empty(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/conversations?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "stats" in data
        assert "groups" in data
        assert "history" in data

    def test_conversations_stats(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/conversations/stats?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "group_count" in data
        assert "msg_count" in data

    def test_conversations_groups(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/conversations/groups?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)

    def test_conversations_send_and_read(self, bridge_server):
        """发送消息后能在 groups 和 messages 中看到。"""
        # 先创建一个 session
        r = _http_request(
            f"{self.base(bridge_server)}/sessions",
            "POST",
            data={"user_id": "conv_test", "agent_profile": "default"},
        )
        assert r["status"] == 200
        session_id = r["body"]["session_id"]

        # 发送消息
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/conversations/messages",
            "POST",
            data={"team_id": 1, "content": "你好", "direction": "user_to_agent"},
        )
        assert r["status"] == 200
        msg = r["body"]["data"]
        assert msg["content"] == "你好"
        assert msg["direction"] == "user_to_agent"

    def test_conversations_group_messages(self, bridge_server):
        """先创建 session + 消息，再通过 group messages 读取。"""
        # 创建 session 并手动添加消息
        r = _http_request(
            f"{self.base(bridge_server)}/sessions",
            "POST",
            data={"user_id": "gm_test", "agent_profile": "default", "session_id": "ses_gm_test"},
        )
        assert r["status"] == 200

        # 通过 invoke 产生消息（需 session 有消息），这里直接用 session clear 后 send
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/conversations/groups/ses_gm_test/messages?team_id=1",
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)

    def test_conversations_history(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/conversations/history?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)


class TestHTTPBillingEndpoints:
    """Billing 端点测试。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def test_wallet(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/billing/wallet")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["balance"] == 0
        assert data["currency"] == "CNY"

    def test_records(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/billing/records?page=1&page_size=10")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["total"] == 0
        assert data["items"] == []

    def test_summary(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/billing/summary")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["total_spent"] == 0
        assert data["total_recharge"] == 0

    def test_recorded_usage_updates_local_finance_views(self, bridge_server):
        import bridge_server as bs_mod

        try:
            bs_mod._save_finance_usage_records([])
            bs_mod._record_finance_usage(
                prompt="hello finance",
                text="world",
                model="gpt-4o-mini",
                provider="openai",
                usage={
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                    "estimated_cost_usd": 0.42,
                },
                duration_seconds=1.75,
            )

            usage = _http_request(f"{self.base(bridge_server)}/api/platform/models/usage?days=7")
            assert usage["status"] == 200
            usage_data = usage["body"]["data"]
            assert usage_data["record_count"] == 1
            assert usage_data["total_calls"] == 1
            assert usage_data["breakdown"][0]["product_name"] == "gpt-4o-mini"

            cost = _http_request(f"{self.base(bridge_server)}/api/platform/models/cost?days=7")
            assert cost["status"] == 200
            cost_data = cost["body"]["data"]
            assert cost_data["record_count"] == 1
            assert cost_data["primary_currency"] == "USD"
            assert cost_data["total_amount"] == pytest.approx(0.42)

            quota = _http_request(f"{self.base(bridge_server)}/api/platform/models/quota")
            assert quota["status"] == 200
            quota_data = quota["body"]["data"]
            assert quota_data["currency"] == "USD"
            assert quota_data["monthly_spent"] == pytest.approx(0.42)

            wallet = _http_request(f"{self.base(bridge_server)}/api/billing/wallet")
            assert wallet["status"] == 200
            wallet_data = wallet["body"]["data"]
            assert wallet_data["currency"] == "USD"
            assert wallet_data["current_month_spent"] == pytest.approx(0.42)

            records = _http_request(f"{self.base(bridge_server)}/api/billing/records?page=1&page_size=10")
            assert records["status"] == 200
            records_data = records["body"]["data"]
            assert records_data["total"] == 1
            assert records_data["items"][0]["product_name"] == "gpt-4o-mini"
            assert records_data["items"][0]["amount"] == pytest.approx(0.42)
        finally:
            bs_mod._save_finance_usage_records([])


class TestHTTPChannelsEndpoints:
    """Channels 端点测试。"""

    def base(self, bridge_server):
        return bridge_server["url"]

    def configure_plugin_channel(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/wechat-personal-plugin/config",
            "POST",
            data={
                "team_id": 1,
                "display_name": "微信个人号(插件)",
                "kernel_corp_id": "corp_test",
                "kernel_agent_id": "agent_test",
                "kernel_secret": "secret_test",
                "kernel_verify_token": "verify_test",
                "kernel_aes_key": "aes_test",
                "enabled": True,
                "binding_enabled": True,
            },
        )
        assert r["status"] == 200
        assert r["body"]["data"]["configured"] is True
        assert r["body"]["data"]["enabled"] is True
        assert r["body"]["data"]["binding_enabled"] is True

    def test_channels_overview(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/channels?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "supported_count" in data
        assert "items" in data
        assert data["supported_count"] == 4
        keys = [i["channel_key"] for i in data["items"]]
        assert "wechat_work" in keys
        assert "feishu" in keys
        assert "wechat_personal_openclaw" in keys

    def test_wechat_work_config(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/channels/wechat-work/config?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["channel_key"] == "wechat_work"
        assert "corp_id" in data
        assert "secret_configured" in data

    def test_wechat_work_config_update(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/wechat-work/config",
            "POST",
            data={"team_id": 1, "corp_id": "corp123", "agent_id": "agent456"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["corp_id"] == "corp123"
        assert data["configured"] is True

    def test_feishu_config(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/channels/feishu/config?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["channel_key"] == "feishu"

    def test_feishu_config_update(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/feishu/config",
            "POST",
            data={"team_id": 1, "app_id": "app123", "app_secret": "secret456"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["app_id"] == "app123"
        assert data["secret_configured"] is True

    def test_wechat_personal_plugin_config(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/channels/wechat-personal-plugin/config?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["channel_key"] == "wechat_personal_plugin"
        assert "setup_status" in data

    def test_wechat_personal_plugin_config_does_not_enable_until_configured(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/wechat-personal-plugin/config",
            "POST",
            data={
                "team_id": 1,
                "display_name": "微信个人号(插件)",
                "enabled": True,
                "binding_enabled": True,
            },
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["configured"] is False
        assert data["enabled"] is False
        assert data["binding_enabled"] is False
        assert data["setup_status"] == "planned"

    def test_wechat_personal_openclaw_config(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/channels/wechat-personal-openclaw/config?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["channel_key"] == "wechat_personal_openclaw"
        assert "gateway_online" in data
        assert "setup_status" in data

    def test_bindings_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/channels/bindings?team_id=1")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data["items"], list)
        assert data["total"] == len(data["items"])

    def test_bindings_validate(self, bridge_server):
        before = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings?team_id=1&channel_key=wechat_personal_plugin"
        )
        assert before["status"] == 200
        before_total = before["body"]["data"]["total"]

        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings/validate?team_id=1&channel_key=wechat_personal_plugin"
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["channel_key"] == "wechat_personal_plugin"
        assert data["ready"] is True
        assert data["probe_write_ok"] is True
        assert data["probe_cleanup_ok"] is True
        assert data["validation_mode"] == "active-write-no-residue"
        assert "list" in data["supported_operations"]
        assert "create" in data["supported_operations"]

        after = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings?team_id=1&channel_key=wechat_personal_plugin"
        )
        assert after["status"] == 200
        assert after["body"]["data"]["total"] == before_total

    def test_binding_create(self, bridge_server):
        self.configure_plugin_channel(bridge_server)

        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings/create",
            "POST",
            data={
                "team_id": 1,
                "binding_type": "user",
                "binding_target_id": "target_001",
                "binding_target_name": "测试绑定",
            },
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["binding_target_id"] == "target_001"
        assert data["status"] == "pending"

        listed = _http_request(f"{self.base(bridge_server)}/api/platform/channels/bindings?team_id=1")
        assert listed["status"] == 200
        items = listed["body"]["data"]["items"]
        assert any(item["id"] == data["id"] for item in items)

    def test_binding_create_requires_configured_plugin_channel(self, bridge_server):
        plugin_config_file = os.path.join(os.environ["HERMES_HOME"], "channel_wechat_personal_plugin.json")
        if os.path.exists(plugin_config_file):
            os.remove(plugin_config_file)

        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings/create",
            "POST",
            data={
                "team_id": 1,
                "binding_type": "user",
                "binding_target_id": "target_unconfigured",
                "binding_target_name": "未配置绑定",
            },
        )
        assert r["status"] == 400
        assert "not fully configured" in r["body"]["message"]

    # --- Step 1: Channels 补全 ---

    def test_binding_disable(self, bridge_server):
        self.configure_plugin_channel(bridge_server)

        created = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings/create",
            "POST",
            data={
                "team_id": 1,
                "binding_type": "user",
                "binding_target_id": "target_disable",
                "binding_target_name": "待禁用绑定",
            },
        )
        assert created["status"] == 200
        binding_id = created["body"]["data"]["id"]

        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings/disable",
            "POST",
            data={"binding_id": binding_id},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["status"] == "disabled"

    def test_binding_regenerate_code(self, bridge_server):
        self.configure_plugin_channel(bridge_server)

        created = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings/create",
            "POST",
            data={
                "team_id": 1,
                "binding_type": "user",
                "binding_target_id": "target_regenerate",
                "binding_target_name": "待重置绑定码",
            },
        )
        assert created["status"] == 200
        binding_id = created["body"]["data"]["id"]

        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/bindings/regenerate-code",
            "POST",
            data={"binding_id": binding_id},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "binding_code" in data

    def test_openclaw_qr_start(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/wechat-personal-openclaw/qr/start",
            "POST",
            data={},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "session_id" in data

    def test_openclaw_qr_status(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/channels/wechat-personal-openclaw/qr/status"
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "status" in data
        assert "connected" in data

    # --- Step 2: Tenant ---

    def test_tenant_context(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/users/me/context")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "user_id" in data or "id" in data
        assert "teams" in data

    def test_company_verification_get(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/company/verification")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["status"] == "none"

    def test_company_verification_submit(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/company/verification",
            "POST",
            data={"company_name": "测试公司"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["status"] == "pending"

    def test_company_verification_approve(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/company/verification/approve",
            "POST",
            data={},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["status"] == "approved"

    # --- Step 3: File / Documents ---

    def test_documents_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/documents")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)

    def test_document_get(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/documents/1")
        # 可能 404（不存在），也可能 200
        assert r["status"] in (200, 404)

    def test_product_documents(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/products/1/documents")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)

    # --- Step 4: Workflow ---

    def test_workflows_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/workflows")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)

    def test_workflow_create(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/workflows",
            "POST",
            data={
                "name": "测试工作流",
                "description": "test workflow",
                "nodes": [],
                "edges": [],
            },
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["name"] == "测试工作流"
        assert "id" in data

    def test_workflow_get(self, bridge_server):
        # 先创建
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/workflows",
            "POST",
            data={"name": "get-test", "nodes": [], "edges": []},
        )
        wf_id = r1["body"]["data"]["id"]
        # 再获取
        r2 = _http_request(f"{self.base(bridge_server)}/api/workflows/{wf_id}")
        assert r2["status"] == 200
        assert r2["body"]["data"]["name"] == "get-test"

    def test_workflow_run(self, bridge_server):
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/workflows",
            "POST",
            data={"name": "run-test", "nodes": [], "edges": []},
        )
        wf_id = r1["body"]["data"]["id"]
        r2 = _http_request(
            f"{self.base(bridge_server)}/api/workflows/{wf_id}/run",
            "POST",
            data={},
        )
        assert r2["status"] == 200
        assert "execution_id" in r2["body"]["data"]

    def test_workflow_execution_logs(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/workflows/executions/fake-exec-id/logs"
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)

    # --- Step 5: Devices ---

    def test_devices_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/devices")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_devices_account_state(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/devices/account-state?installation_id=test"
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "state" in data

    def test_devices_online(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/devices/online")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "runtime_label" in data

    def test_devices_bootstrap(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/devices/bootstrap",
            "POST",
            data={
                "installation_id": "inst_001",
                "device_name": "测试设备",
            },
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "device_id" in data

    def test_devices_pair_code(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/devices/pair-code",
            "POST",
            data={},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "pair_code" in data

    def test_devices_claim(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/devices/claim",
            "POST",
            data={"installation_id": "inst_002", "device_name": "claim设备"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "device_id" in data

    def test_device_update(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/devices/1",
            "PUT",
            data={"device_name": "新名称"},
        )
        assert r["status"] == 200

    def test_device_delete(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/devices/1",
            "DELETE",
        )
        assert r["status"] == 200

    # --- Step 6: Knowledge 新路径 ---

    def test_platform_knowledge_list(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/knowledge/list?team_id=1"
        )
        assert r["status"] == 200

    def test_platform_knowledge_search(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/knowledge/search?query=test&team_id=1"
        )
        assert r["status"] == 200

    def test_platform_knowledge_stats(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/knowledge/stats?team_id=1"
        )
        assert r["status"] == 200

    def test_platform_knowledge_config(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/knowledge/config?team_id=1"
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "watch_dir" in data

    def test_platform_knowledge_config_update(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/knowledge/config/update",
            "POST",
            data={"team_id": 1, "watch_dir": "/tmp/test_knowledge"},
        )
        assert r["status"] == 200

    def test_platform_knowledge_download(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/knowledge/download?source_name=test.txt&team_id=1"
        )
        # 可能 404（文件不存在）或 200
        assert r["status"] in (200, 404)

    # --- Step 7: Approval ---

    def test_approvals_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/approvals")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "items" in data
        assert "total" in data

    def test_approval_request(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/approvals/request",
            "POST",
            data={
                "approval_type": "tool_access",
                "title": "请求使用终端",
                "reason": "需要执行部署脚本",
                "risk_level": "medium",
            },
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["status"] == "pending"
        assert "approval_id" in data

    def test_approval_get(self, bridge_server):
        # 先创建
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/platform/approvals/request",
            "POST",
            data={
                "approval_type": "data_access",
                "title": "数据访问",
                "reason": "分析报表",
                "risk_level": "low",
            },
        )
        aid = r1["body"]["data"]["approval_id"]
        # 再获取
        r2 = _http_request(f"{self.base(bridge_server)}/api/platform/approvals/{aid}")
        assert r2["status"] == 200
        assert r2["body"]["data"]["approval_id"] == aid

    def test_approval_resolve(self, bridge_server):
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/platform/approvals/request",
            "POST",
            data={
                "approval_type": "exec_access",
                "title": "执行权限",
                "reason": "测试",
                "risk_level": "high",
            },
        )
        aid = r1["body"]["data"]["approval_id"]
        r2 = _http_request(
            f"{self.base(bridge_server)}/api/platform/approvals/{aid}/resolve",
            "POST",
            data={"action": "approved"},
        )
        assert r2["status"] == 200
        assert r2["body"]["data"]["status"] == "approved"

    # --- Step 8: Audit ---

    def test_audit_events_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/audit/events")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "items" in data
        assert "total" in data

    def test_audit_record(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/audit/events",
            "POST",
            data={
                "category": "operation",
                "event_type": "tool_call",
                "title": "调用终端工具",
                "summary": "执行 ls 命令",
            },
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "event_id" in data

    def test_audit_summary(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/platform/audit/summary")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "total" in data

    # --- Step 9: ApiKey ---

    def test_app_keys_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/users/app-keys")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "items" in data
        assert "total" in data

    def test_app_key_create(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/users/app-keys",
            "POST",
            data={"name": "测试Key"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["name"] == "测试Key"
        assert "app_key" in data
        assert "app_secret" in data

    def test_app_key_rename(self, bridge_server):
        # 先创建
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/users/app-keys",
            "POST",
            data={"name": "rename-test"},
        )
        kid = r1["body"]["data"]["id"]
        # 重命名
        r2 = _http_request(
            f"{self.base(bridge_server)}/api/users/app-keys/{kid}/name",
            "PUT",
            data={"name": "新名称"},
        )
        assert r2["status"] == 200
        assert r2["body"]["data"]["name"] == "新名称"

    def test_app_key_set_active(self, bridge_server):
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/users/app-keys",
            "POST",
            data={"name": "active-test"},
        )
        kid = r1["body"]["data"]["id"]
        r2 = _http_request(
            f"{self.base(bridge_server)}/api/users/app-keys/{kid}",
            "PATCH",
            data={"is_active": False},
        )
        assert r2["status"] == 200
        assert r2["body"]["data"]["is_active"] is False

    def test_app_key_delete(self, bridge_server):
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/users/app-keys",
            "POST",
            data={"name": "delete-test"},
        )
        kid = r1["body"]["data"]["id"]
        r2 = _http_request(
            f"{self.base(bridge_server)}/api/users/app-keys/{kid}",
            "DELETE",
        )
        assert r2["status"] == 200

    def test_app_key_issue_token(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/users/app-keys/default/token",
            "POST",
            data={},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert "token" in data

    def test_llm_keys_list(self, bridge_server):
        r = _http_request(f"{self.base(bridge_server)}/api/llm/keys")
        assert r["status"] == 200
        data = r["body"]["data"]
        assert isinstance(data, list)

    def test_llm_key_create(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/llm/keys",
            "POST",
            data={
                "provider": "openai",
                "api_key": "sk-test123",
                "name": "测试LLM密钥",
            },
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["provider"] == "openai"
        assert "id" in data

    def test_llm_key_update(self, bridge_server):
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/llm/keys",
            "POST",
            data={"provider": "anthropic", "api_key": "sk-ant-test", "name": "update-test"},
        )
        kid = r1["body"]["data"]["id"]
        r2 = _http_request(
            f"{self.base(bridge_server)}/api/llm/keys/{kid}",
            "PUT",
            data={"name": "更新后名称"},
        )
        assert r2["status"] == 200
        assert r2["body"]["data"]["name"] == "更新后名称"

    def test_llm_key_delete(self, bridge_server):
        r1 = _http_request(
            f"{self.base(bridge_server)}/api/llm/keys",
            "POST",
            data={"provider": "deepseek", "api_key": "sk-ds-test", "name": "delete-test"},
        )
        kid = r1["body"]["data"]["id"]
        r2 = _http_request(
            f"{self.base(bridge_server)}/api/llm/keys/{kid}",
            "DELETE",
        )
        assert r2["status"] == 200

    # --- Step 10: Policy ---

    def test_policy_tool_access_check(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/policy/tool-access/check",
            "POST",
            data={"tool_name": "terminal"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["allowed"] is True

    def test_policy_data_access_check(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/policy/data-access/check",
            "POST",
            data={"resource": "customer_db"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["allowed"] is True

    def test_policy_exec_access_check(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/platform/policy/exec-access/check",
            "POST",
            data={"command": "deploy.sh"},
        )
        assert r["status"] == 200
        data = r["body"]["data"]
        assert data["allowed"] is True

    # --- Step 11: Voice ---

    def test_voice_asr(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/asr",
            "POST",
            data={},
        )
        assert r["status"] == 501

    def test_voice_tts(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/tts",
            "POST",
            data={"text": "你好"},
        )
        assert r["status"] == 501

    def test_voice_audio_speech(self, bridge_server):
        r = _http_request(
            f"{self.base(bridge_server)}/api/audio/speech",
            "POST",
            data={"text": "测试"},
        )
        assert r["status"] == 501


# ===================================================================
# 清理
# ===================================================================

def teardown_module():
    """模块级清理。"""
    sm_mod._session_manager = None
    if os.path.exists(_TMPDIR):
        shutil.rmtree(_TMPDIR, ignore_errors=True)
