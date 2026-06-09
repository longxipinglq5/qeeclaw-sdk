import importlib.util
import os
import sys
from pathlib import Path


def _load_bridge(monkeypatch, tmp_path):
    bridge_dir = Path(__file__).parent
    env_keys = [
        "CENTAUR_RUNTIME_ENV_FILE",
        "CENTAUR_MODEL_API_KEY",
        "NEXUS_API_KEY",
        "NEXUS_URL",
        "CENTAUR_MODEL_BASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "HERMES_PROVIDER",
        "HERMES_MODEL",
        "QEECLAW_LOCAL_LLM_BASE_URL",
        "QEECLAW_LOCAL_LLM_API_KEY",
    ]
    intended_env = {key: os.environ[key] for key in env_keys if key in os.environ}
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in intended_env.items():
        monkeypatch.setenv(key, value)
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


def test_cloud_runtime_uses_qeeshu_platform_even_with_deepseek_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_PROVIDER", "deepseek")
    monkeypatch.setenv("HERMES_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    bridge = _load_bridge(monkeypatch, tmp_path)

    runtime = bridge._resolve_runtime_client_config(None, None)

    assert runtime["provider"] == "qeeshu-platform"
    assert runtime["model"] == "deepseek-chat"
    assert runtime["base_url"] == "https://paas.qeeshu.com"
    assert runtime["api_key"] == "sk-deepseek-test"
    assert runtime["runtime_scope"] == ""
    assert bridge._runtime_client_is_configured(runtime) is True


def test_cloud_runtime_uses_fixed_qeeshu_platform_url(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_PROVIDER", "deepseek")
    monkeypatch.setenv("HERMES_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-key")
    bridge = _load_bridge(monkeypatch, tmp_path)

    runtime = bridge._resolve_runtime_client_config(None, None)

    assert runtime["provider"] == "qeeshu-platform"
    assert runtime["base_url"] == "https://paas.qeeshu.com"
    assert runtime["api_key"] == "local-key"


def test_provisioned_model_key_overrides_local_env_key(tmp_path, monkeypatch):
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "CENTAUR_MODEL_API_KEY=cloud-key\n"
        "NEXUS_API_KEY=cloud-nexus-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CENTAUR_RUNTIME_ENV_FILE", str(runtime_env))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-key")
    monkeypatch.setenv("NEXUS_API_KEY", "local-nexus-key")
    bridge = _load_bridge(monkeypatch, tmp_path)

    runtime = bridge._resolve_runtime_client_config(None, None)

    assert runtime["provider"] == "qeeshu-platform"
    assert runtime["base_url"] == "https://paas.qeeshu.com"
    assert runtime["api_key"] == "cloud-key"
    assert bridge.os.environ["NEXUS_API_KEY"] == "cloud-nexus-key"


def test_model_key_populates_nexus_key_for_platform_features(tmp_path, monkeypatch):
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text("CENTAUR_MODEL_API_KEY=cloud-key\n", encoding="utf-8")
    monkeypatch.setenv("CENTAUR_RUNTIME_ENV_FILE", str(runtime_env))
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)
    bridge = _load_bridge(monkeypatch, tmp_path)

    runtime = bridge._resolve_runtime_client_config(None, None)

    assert runtime["api_key"] == "cloud-key"
    assert bridge.os.environ["NEXUS_URL"] == "https://paas.qeeshu.com"
    assert bridge.os.environ["NEXUS_API_KEY"] == "cloud-key"


def test_release_runtime_scope_uses_platform_and_does_not_default_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_PROVIDER", "deepseek")
    monkeypatch.setenv("HERMES_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    bridge = _load_bridge(monkeypatch, tmp_path)

    cloud_runtime = bridge._resolve_runtime_client_config(None, None, runtime_scope=None)
    local_runtime = bridge._resolve_runtime_client_config(None, None, runtime_scope="local")

    assert cloud_runtime["provider"] == "qeeshu-platform"
    assert cloud_runtime["runtime_scope"] == ""
    assert cloud_runtime["base_url"] == "https://paas.qeeshu.com"
    assert not bridge._is_local_runtime_base_url(cloud_runtime["base_url"])
    assert local_runtime["provider"] == "local"
    assert local_runtime["runtime_scope"] == "local"


def test_local_runtime_scope_keeps_local_model_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("CENTAUR_MODEL_API_KEY", "cloud-key")
    monkeypatch.setenv("QEECLAW_LOCAL_LLM_BASE_URL", "http://127.0.0.1:8090/v1")
    monkeypatch.setenv("QEECLAW_LOCAL_LLM_API_KEY", "local-runtime-key")
    bridge = _load_bridge(monkeypatch, tmp_path)

    runtime = bridge._resolve_runtime_client_config(None, None, runtime_scope="local")

    assert runtime["provider"] == "local"
    assert runtime["base_url"] == "http://127.0.0.1:8090/v1"
    assert runtime["api_key"] == "local-runtime-key"
    assert runtime["runtime_scope"] == "local"
