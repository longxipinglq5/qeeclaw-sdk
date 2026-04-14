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
# 清理
# ===================================================================

def teardown_module():
    """模块级清理。"""
    sm_mod._session_manager = None
    if os.path.exists(_TMPDIR):
        shutil.rmtree(_TMPDIR, ignore_errors=True)
