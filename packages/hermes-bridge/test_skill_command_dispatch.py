import importlib.util
import json
import os
import sys
from pathlib import Path


class _FakeRFile:
    def __init__(self, body):
        self.body = body

    def read(self, _length):
        return self.body


class _FakeWFile:
    def __init__(self):
        self.data = b""

    def write(self, data):
        self.data += data


class _FakeHandler:
    def __init__(self, body):
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


class _FakeRouteHandler(_FakeHandler):
    def __init__(self, body):
        super().__init__(body)
        self.path = "/api/platform/models/invoke"
        self.routed = None

    def _handle_invoke(self, **kwargs):
        self.routed = ("invoke", kwargs)

    def _handle_llm_proxy_to_backend(self, *args):
        self.routed = ("proxy", args)


class _FakeSession:
    session_id = "sess-skill"
    agent_profile = "spark"
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
    available = True

    def __init__(self):
        self.invocations = []

    def invoke(self, **kwargs):
        self.invocations.append(kwargs)
        return {"text": "ok", "model": "fake-model", "provider": "fake-provider"}


def _load_bridge(monkeypatch, tmp_path):
    bridge_dir = Path(__file__).parent
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    monkeypatch.setenv("QEECLAW_HERMES_AGENT_DIR", str(tmp_path))
    if str(bridge_dir) not in sys.path:
        sys.path.insert(0, str(bridge_dir))
    spec = importlib.util.spec_from_file_location(
        "bridge_skill_dispatch_under_test",
        bridge_dir / "bridge_server.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["bridge_skill_dispatch_under_test"] = module
    spec.loader.exec_module(module)
    return module


def _load_bridge_with_hermes(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    hermes_agent_dir = repo_root / "vendor" / "hermes-agent"
    bridge = _load_bridge(monkeypatch, tmp_path)
    monkeypatch.setenv("QEECLAW_HERMES_AGENT_DIR", str(hermes_agent_dir))
    bridge.HERMES_AGENT_DIR = str(hermes_agent_dir)
    bridge._hermes_loaded = False
    bridge._hermes_error = None
    if str(hermes_agent_dir) not in sys.path:
        sys.path.insert(0, str(hermes_agent_dir))
    for name in ("agent.skill_commands", "tools.skills_tool"):
        sys.modules.pop(name, None)
    return bridge


def _write_skill(home: Path, name: str, description: str):
    skill_dir = home / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join([
            "---",
            f"name: {name}",
            f"description: {description}",
            "---",
            "",
            f"# {name}",
            "",
            f"Follow the {name} instructions.",
        ]),
        encoding="utf-8",
    )


def _install_fakes(monkeypatch, bridge, resolve_result="/moments-copywriter", built_message="[skill] write copy"):
    sm = _FakeSessionManager()
    pool = _FakePool()
    monkeypatch.setattr(bridge, "get_agent_pool", lambda: pool)
    monkeypatch.setitem(sys.modules, "session_manager", type("_SM", (), {"get_session_manager": lambda: sm}))

    calls = []

    def scan():
        calls.append(("scan", bridge.os.environ.get("HERMES_HOME")))

    def resolve(command):
        calls.append(("resolve", command, bridge.os.environ.get("HERMES_HOME")))
        return resolve_result

    def build(cmd_key, user_instruction, task_id=None, runtime_note=""):
        calls.append(("build", cmd_key, user_instruction, task_id, runtime_note, bridge.os.environ.get("HERMES_HOME")))
        return built_message

    fake_skill_commands = type(
        "_SkillCommands",
        (),
        {
            "scan_skill_commands": staticmethod(scan),
            "resolve_skill_command_key": staticmethod(resolve),
            "build_skill_invocation_message": staticmethod(build),
        },
    )
    monkeypatch.setitem(sys.modules, "agent.skill_commands", fake_skill_commands)
    return sm, pool, calls


def _invoke(bridge, payload):
    body = json.dumps(payload).encode("utf-8")
    handler = _FakeHandler(body)
    bridge.BridgeRequestHandler._handle_invoke(handler)
    response = json.loads(handler.wfile.data.decode("utf-8"))
    return handler, response


def test_invoke_uses_explicit_skill_command_dispatch(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    _sm, pool, calls = _install_fakes(monkeypatch, bridge)
    profile_home = str(tmp_path / "profiles" / "spark")
    monkeypatch.setattr(pool, "_ensure_profile_home", lambda profile_name: str(tmp_path / "profiles" / profile_name), raising=False)

    handler, payload = _invoke(bridge, {
        "prompt": "新品上市",
        "agent_profile": "spark",
        "skill_command": "moments-copywriter",
        "task_id": "task-1",
    })

    assert handler.status == 200
    assert payload["_skill_command"] == "moments-copywriter"
    assert payload["_skill_command_resolved"] == "/moments-copywriter"
    assert pool.invocations[0]["prompt"] == "[skill] write copy"
    assert calls == [
        ("scan", profile_home),
        ("resolve", "moments-copywriter", profile_home),
        ("build", "/moments-copywriter", "新品上市", "task-1", "", profile_home),
    ]


def test_invoke_uses_slash_prompt_dispatch(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    _sm, pool, calls = _install_fakes(monkeypatch, bridge)
    profile_home = str(tmp_path / "profiles" / "spark")
    monkeypatch.setattr(pool, "_ensure_profile_home", lambda profile_name: str(tmp_path / "profiles" / profile_name), raising=False)

    handler, payload = _invoke(bridge, {
        "prompt": "/moments-copywriter 新品上市",
        "agent_profile": "spark",
    })

    assert handler.status == 200
    assert payload["_skill_command"] == "moments-copywriter"
    assert payload["_skill_command_resolved"] == "/moments-copywriter"
    assert pool.invocations[0]["prompt"] == "[skill] write copy"
    assert calls == [
        ("scan", profile_home),
        ("resolve", "moments-copywriter", profile_home),
        ("build", "/moments-copywriter", "新品上市", None, "", profile_home),
    ]


def test_invoke_returns_unknown_skill_command(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    _install_fakes(monkeypatch, bridge, resolve_result=None)

    handler, payload = _invoke(bridge, {
        "prompt": "新品上市",
        "agent_profile": "spark",
        "skill_command": "missing-skill",
    })

    assert handler.status == 400
    assert payload["error"]["code"] == "unknown_skill_command"
    assert payload["error"]["skill_command"] == "missing-skill"


def test_invoke_leaves_plain_prompt_unchanged(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    _sm, pool, calls = _install_fakes(monkeypatch, bridge)

    handler, payload = _invoke(bridge, {
        "prompt": "普通问题",
        "agent_profile": "spark",
    })

    assert handler.status == 200
    assert "_skill_command" not in payload
    assert pool.invocations[0]["prompt"] == "普通问题"
    assert calls == []


def test_platform_model_route_uses_bridge_invoke_when_skill_metadata_present(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    body = json.dumps({
        "prompt": "新品上市",
        "skill_command": "moments-copywriter",
    }).encode("utf-8")
    handler = _FakeRouteHandler(body)

    bridge.BridgeRequestHandler._handle_platform_model_invoke(handler)

    assert handler.routed == ("invoke", {"platform_response": False})


def test_platform_model_route_keeps_backend_proxy_for_plain_prompt(tmp_path, monkeypatch):
    bridge = _load_bridge(monkeypatch, tmp_path)
    body = json.dumps({"prompt": "普通问题"}).encode("utf-8")
    handler = _FakeRouteHandler(body)

    bridge.BridgeRequestHandler._handle_platform_model_invoke(handler)

    assert handler.routed == ("proxy", ("POST", "/api/platform/models/invoke"))


def test_real_hermes_skill_resolution_uses_requested_profile_home(tmp_path, monkeypatch):
    bridge = _load_bridge_with_hermes(monkeypatch, tmp_path)
    profile_a = tmp_path / "profiles" / "alpha"
    profile_b = tmp_path / "profiles" / "beta"
    _write_skill(profile_a, "alpha-skill", "Alpha only")
    _write_skill(profile_b, "beta-skill", "Beta only")

    os.environ["HERMES_HOME"] = str(profile_a)
    import agent.skill_commands as skill_commands
    import tools.skills_tool as skills_tool

    skill_commands.scan_skill_commands()
    assert skill_commands.resolve_skill_command_key("alpha-skill") == "/alpha-skill"
    assert skill_commands.resolve_skill_command_key("beta-skill") is None
    assert skills_tool.SKILLS_DIR == profile_a / "skills"

    prompt, metadata, error = bridge._resolve_skill_invocation_prompt(
        "请执行 beta",
        {"skill_command": "beta-skill"},
        hermes_home=str(profile_b),
    )

    assert error is None
    assert metadata == {
        "skill_command": "beta-skill",
        "skill_command_resolved": "/beta-skill",
    }
    assert "Beta only" in prompt
    assert "请执行 beta" in prompt
    assert os.environ["HERMES_HOME"] == str(profile_a)
    assert skills_tool.SKILLS_DIR == profile_a / "skills"
