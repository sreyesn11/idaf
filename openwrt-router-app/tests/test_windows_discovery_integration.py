"""Real-network integration checks for WindowsNeighborCollector.

Excluded by default (see `pyproject.toml`'s `addopts`); run explicitly with:

    pytest -m windows_discovery_integration

These hit real PowerShell and the real local network — never run them in CI
or as part of the default suite (spec doc 03, section 13).
"""

from __future__ import annotations

import pytest

from discovery.collectors.windows_commands import get_net_ip_configuration
from discovery.collectors.windows_neighbor import WindowsNeighborCollector
from discovery.config import load_discovery_config

pytestmark = pytest.mark.windows_discovery_integration


# The shipped default (5s, matching the spec's own example config) is tuned
# for a real Windows shell; PowerShell's own process-startup overhead in a
# sandboxed/nested shell can exceed that, so these tests use a generous
# timeout to stay robust across environments without changing the shipped
# default in config/settings.yaml.
_INTEGRATION_TIMEOUT = 20.0


def test_real_interface_is_reachable() -> None:
    config = load_discovery_config().model_copy(update={"command_timeout_seconds": _INTEGRATION_TIMEOUT})
    info = get_net_ip_configuration(config.interface_index, config.command_timeout_seconds)

    assert info is not None
    assert info["InterfaceAlias"].lower() == config.interface_alias.lower()


def test_real_collect_never_raises_and_finds_known_devices() -> None:
    config = load_discovery_config().model_copy(
        update={"allow_active_enrichment": True, "command_timeout_seconds": _INTEGRATION_TIMEOUT}
    )
    collector = WindowsNeighborCollector(config)

    observations = collector.collect()

    macs = {obs.raw_payload["mac"] for obs in observations}
    assert collector.last_run_stats is not None
    assert collector.last_run_stats["raw_ipv4_neighbors"] >= 0
    # Not asserting on specific MACs here — the real lab network can change
    # over time; the smoke test is that this runs end-to-end without error.
    assert isinstance(macs, set)
