import importlib.util
import json
import sys
from pathlib import Path


class _FakeWFile:
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data


class _FakeHandler:
    def __init__(self, bridge, body):
        self._bridge = bridge
        self.headers = {"Content-Length": str(len(body))}
        self.rfile = _FakeRFile(body)
        self.wfile = _FakeWFile()
        self.status = None
        self.response_headers = []

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.response_headers.append((key, value))

    def end_headers(self):
        pass


class _FakeRFile:
    def __init__(self, body):
        self.body = body

    def read(self, _length):
        return self.body


class _FakeSession:
    session_id = "sess-test"
    agent_profile = "agent-a"
    turn_count = 0

    def get_messages(self, max_turns=20):
        return []


class _FakeSessionManager:
    def __init__(self):
        self.appended = []

    def get_or_create_session(self, **_kwargs):
        return _FakeSession()

    def get_profile(self, _agent_profile):
        return None

    def append_turn(self, session_id, prompt, assistant_text):
        self.appended.append((session_id, prompt, assistant_text))


class _FakePool:
    available = False

    def __init__(self):
        self.system_prompt = None

    def invoke(self, **kwargs):
        self.system_prompt = kwargs.get("system_prompt")
        return {"text": "ok", "model": "fake", "provider": "fake"}


def _load_bridge(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    sys.path.insert(0, str(Path(__file__).parent))
    spec = importlib.util.spec_from_file_location(
        "bridge_under_test",
        Path(__file__).with_name("bridge_server.py"),
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["bridge_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_invoke_injects_local_memory_context(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    sm = _FakeSessionManager()
    pool = _FakePool()
    monkeypatch.setattr(bridge, "get_agent_pool", lambda: pool)
    monkeypatch.setitem(sys.modules, "session_manager", type("_SM", (), {"get_session_manager": lambda: sm}))

    from memory_store import store_memory

    store_memory(
        content="用户偏好：回答销售问题时优先使用中文。",
        category="preference",
        importance=0.9,
        agent_id="agent-a",
        runtime_type="openclaw",
        skip_duplicate_check=True,
    )

    body = json.dumps({
        "prompt": "销售问题怎么回答",
        "agent_profile": "agent-a",
        "runtime_type": "openclaw",
        "use_knowledge": False,
    }).encode("utf-8")
    handler = _FakeHandler(bridge, body)

    bridge.BridgeRequestHandler._handle_invoke(handler)

    assert handler.status == 200
    payload = json.loads(handler.wfile.data.decode("utf-8"))
    assert payload["_memory_used"] is True
    assert "【本地记忆】" in pool.system_prompt
    assert "用户偏好" in pool.system_prompt


def test_invoke_uses_session_profile_for_memory_scope(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    sm = _FakeSessionManager()
    pool = _FakePool()
    monkeypatch.setattr(bridge, "get_agent_pool", lambda: pool)
    monkeypatch.setitem(sys.modules, "session_manager", type("_SM", (), {"get_session_manager": lambda: sm}))

    from memory_store import store_memory

    store_memory(
        content="真实 profile 记忆：客户要求本地向量库。",
        category="preference",
        importance=0.9,
        agent_id="agent-a",
        runtime_type="openclaw",
        skip_duplicate_check=True,
    )
    store_memory(
        content="默认 profile 记忆：这条不应该注入。",
        category="preference",
        importance=0.9,
        agent_id="default",
        runtime_type="openclaw",
        skip_duplicate_check=True,
    )

    body = json.dumps({
        "prompt": "客户问记忆中心怎么部署",
        "session_id": "sess-test",
        "runtime_type": "openclaw",
        "use_knowledge": False,
    }).encode("utf-8")
    handler = _FakeHandler(bridge, body)

    bridge.BridgeRequestHandler._handle_invoke(handler)

    assert handler.status == 200
    payload = json.loads(handler.wfile.data.decode("utf-8"))
    assert payload["_memory_used"] is True
    assert payload["agent_profile"] == "agent-a"
    assert "真实 profile 记忆" in pool.system_prompt
    assert "默认 profile 记忆" not in pool.system_prompt


def test_invoke_can_disable_memory_context(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    sm = _FakeSessionManager()
    pool = _FakePool()
    monkeypatch.setattr(bridge, "get_agent_pool", lambda: pool)
    monkeypatch.setitem(sys.modules, "session_manager", type("_SM", (), {"get_session_manager": lambda: sm}))

    from memory_store import store_memory

    store_memory(
        content="禁用测试记忆：不应该注入。",
        category="preference",
        importance=0.9,
        agent_id="agent-a",
        runtime_type="openclaw",
        skip_duplicate_check=True,
    )

    body = json.dumps({
        "prompt": "禁用测试",
        "agent_profile": "agent-a",
        "runtime_type": "openclaw",
        "use_knowledge": False,
        "useMemory": False,
    }).encode("utf-8")
    handler = _FakeHandler(bridge, body)

    bridge.BridgeRequestHandler._handle_invoke(handler)

    payload = json.loads(handler.wfile.data.decode("utf-8"))
    assert "_memory_used" not in payload
    assert "【本地记忆】" not in (pool.system_prompt or "")


def test_default_scope_does_not_fallback_to_unrelated_recent_memory(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)

    from memory_store import store_memory

    store_memory(
        content="默认记忆：不匹配查询时不能靠空查询注入。",
        category="preference",
        importance=0.9,
        agent_id="default",
        runtime_type="openclaw",
        skip_duplicate_check=True,
    )

    context = bridge._build_memory_context(
        "完全不匹配的问题",
        {"runtime_type": "openclaw"},
        agent_profile="default",
    )
    assert context == ""
