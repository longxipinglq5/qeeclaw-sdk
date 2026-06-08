import importlib.util
import os
import sys
from pathlib import Path


def _load_bridge_config(monkeypatch, tmp_path):
    bridge_dir = Path(__file__).parent
    env_keys = [
        "CENTAUR_RUNTIME_ENV_FILE",
        "CENTAUR_MODEL_API_KEY",
        "NEXUS_API_KEY",
        "NEXUS_URL",
        "CENTAUR_MODEL_BASE_URL",
        "DEEPSEEK_API_KEY",
    ]
    intended_env = {key: os.environ[key] for key in env_keys if key in os.environ}
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    for key, value in intended_env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    monkeypatch.setenv("QEECLAW_HERMES_AGENT_DIR", str(tmp_path))
    module_name = "bridge_config_provisioning_under_test"
    if str(bridge_dir) not in sys.path:
        sys.path.insert(0, str(bridge_dir))
    spec = importlib.util.spec_from_file_location(
        module_name,
        bridge_dir / "bridge" / "config.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_bridge_config_uses_fixed_platform_url_and_provisioned_key(tmp_path, monkeypatch):
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "CENTAUR_MODEL_API_KEY=cloud-key\n"
        "NEXUS_API_KEY=cloud-nexus-key\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CENTAUR_RUNTIME_ENV_FILE", str(runtime_env))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "local-key")
    monkeypatch.setenv("NEXUS_URL", "https://customer.example.com")

    config = _load_bridge_config(monkeypatch, tmp_path)

    assert config.settings.hermes_provider == "qeeshu-platform"
    assert config.settings.deepseek_base_url == "https://paas.qeeshu.com"
    assert config.settings.deepseek_api_key == "cloud-key"
    assert config.os.environ["NEXUS_URL"] == "https://paas.qeeshu.com"
    assert config.os.environ["NEXUS_API_KEY"] == "cloud-nexus-key"


def test_bridge_config_maps_model_key_to_nexus_key_when_missing(tmp_path, monkeypatch):
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text("CENTAUR_MODEL_API_KEY=cloud-key\n", encoding="utf-8")
    monkeypatch.setenv("CENTAUR_RUNTIME_ENV_FILE", str(runtime_env))
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)

    config = _load_bridge_config(monkeypatch, tmp_path)

    assert config.settings.deepseek_api_key == "cloud-key"
    assert config.os.environ["NEXUS_URL"] == "https://paas.qeeshu.com"
    assert config.os.environ["NEXUS_API_KEY"] == "cloud-key"
