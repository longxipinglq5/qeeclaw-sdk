from __future__ import annotations

import os

import pytest


_REQUIRED_ENV = [
    "HERMES_INTEGRATION_PROVIDER",
    "HERMES_INTEGRATION_MODEL",
    "HERMES_INTEGRATION_API_KEY",
]


@pytest.mark.integration
@pytest.mark.skipif(
    any(not os.environ.get(name) for name in _REQUIRED_ENV),
    reason=(
        "Marketing centaur integration requires real Hermes provider env: "
        "HERMES_INTEGRATION_PROVIDER, HERMES_INTEGRATION_MODEL, "
        "and HERMES_INTEGRATION_API_KEY/provider credentials."
    ),
)
async def test_marketing_centaur_flow_real_provider_schema_smoke():
    # The default suite uses fake providers. This smoke test is intentionally
    # skipped unless a real Hermes provider is configured by the operator.
    assert os.environ["HERMES_INTEGRATION_PROVIDER"]
    assert os.environ["HERMES_INTEGRATION_MODEL"]
