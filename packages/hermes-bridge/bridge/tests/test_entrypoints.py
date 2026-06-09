from __future__ import annotations

import sys
from pathlib import Path


if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def test_bridge_package_exposes_only_bridge_main_entrypoint() -> None:
    data = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text())

    scripts = data["project"]["scripts"]
    assert scripts["qeeclaw-hermes-bridge"] == "bridge.main:cli"
    assert scripts["qeeclaw-bridge"] == "bridge.main:cli"

    py_modules = data["tool"]["setuptools"].get("py-modules", [])
    assert "bridge_server" not in py_modules
    assert not (PACKAGE_ROOT / "bridge_server.py").exists()
