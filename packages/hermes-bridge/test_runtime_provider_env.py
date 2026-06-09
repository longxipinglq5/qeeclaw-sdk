import importlib.util
import sys
from pathlib import Path


def _load_bridge(monkeypatch, tmp_path):
    bridge_dir = Path(__file__).parent
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    monkeypatch.setenv("QEECLAW_HERMES_AGENT_DIR", str(tmp_path))
    if str(bridge_dir) not in sys.path:
        sys.path.insert(0, str(bridge_dir))
    spec = importlib.util.spec_from_file_location(
        "bridge_runtime_provider_env_under_test",
        bridge_dir / "bridge" / "legacy_server.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["bridge_runtime_provider_env_under_test"] = module
    spec.loader.exec_module(module)
    return module


def test_deepseek_env_resolves_openai_compatible_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_PROVIDER", "deepseek")
    monkeypatch.setenv("HERMES_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    bridge = _load_bridge(monkeypatch, tmp_path)

    runtime = bridge._resolve_runtime_client_config(None, None)

    assert runtime["provider"] == "deepseek"
    assert runtime["model"] == "deepseek-chat"
    assert runtime["base_url"] == "https://api.deepseek.com/v1"
    assert runtime["api_key"] == "sk-deepseek-test"
    assert runtime["runtime_scope"] == ""
    assert bridge._runtime_client_is_configured(runtime) is True


def test_release_runtime_scope_does_not_default_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_PROVIDER", "deepseek")
    monkeypatch.setenv("HERMES_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    bridge = _load_bridge(monkeypatch, tmp_path)

    cloud_runtime = bridge._resolve_runtime_client_config(None, None, runtime_scope=None)
    local_runtime = bridge._resolve_runtime_client_config(None, None, runtime_scope="local")

    assert cloud_runtime["provider"] == "deepseek"
    assert cloud_runtime["runtime_scope"] == ""
    assert not bridge._is_local_runtime_base_url(cloud_runtime["base_url"])
    assert local_runtime["provider"] == "local"
    assert local_runtime["runtime_scope"] == "local"
