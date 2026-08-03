from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from core.constants import SETTINGS_FILE


class DiscoveryConfig(BaseModel):
    """Settings for the discovery module (spec section 9).

    Absence of a `discovery:` block in settings.yaml is the normal case
    today, not a misconfiguration — unlike `diagnostics/thresholds.py`,
    missing config here just means "use the safe defaults", never an error.
    """

    enabled: bool = True
    mode: str = "simulated"  # "simulated" | "windows_local"
    interface_alias: str = "Ethernet"
    interface_index: int | None = None
    allow_active_enrichment: bool = False
    allowed_probe_ports: list[int] = Field(default_factory=lambda: [22, 80, 443])
    command_timeout_seconds: float = 15.0
    max_parallel_probes: int = 3
    retain_failed_observations: bool = True


def load_discovery_config(path: Path = SETTINGS_FILE) -> DiscoveryConfig:
    if not path.exists():
        return DiscoveryConfig()

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    section = raw.get("discovery")
    if not section:
        return DiscoveryConfig()

    return DiscoveryConfig.model_validate(section)
