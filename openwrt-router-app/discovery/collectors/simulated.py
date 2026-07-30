from __future__ import annotations

import json
from pathlib import Path

from core.exceptions import DiscoveryFixtureError
from discovery.enums import CollectorType, ObservationType
from discovery.models import RawDiscoveryObservation

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def list_available_fixtures() -> list[Path]:
    if not FIXTURES_DIR.exists():
        return []
    return sorted(FIXTURES_DIR.glob("*.json"))


class SimulatedDiscoveryCollector:
    """Reads a JSON fixture and produces the exact same
    `RawDiscoveryObservation` shape a real collector would.

    This is the only collector implemented in this version (spec section 2:
    no real SSH/VPN/network access to the lab yet) — everything downstream
    of `collect()` is identical for a future real collector.
    """

    def __init__(self, fixture_path: Path) -> None:
        self._fixture_path = fixture_path
        self.collector_type = CollectorType.SIMULATED_ROUTER

    def collect(self) -> list[RawDiscoveryObservation]:
        try:
            raw_text = self._fixture_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except OSError as exc:
            raise DiscoveryFixtureError(f"No se pudo leer el fixture: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise DiscoveryFixtureError(f"El fixture no es JSON válido: {exc}") from exc

        try:
            collector_id = data["collector_id"]
            collector_type = CollectorType(data["collector_type"])
            default_observed_at = data["observed_at"]
        except (KeyError, ValueError) as exc:
            raise DiscoveryFixtureError(f"El fixture no tiene el formato esperado: {exc}") from exc

        self.collector_type = collector_type
        observations: list[RawDiscoveryObservation] = []
        for index, item in enumerate(data.get("observations", [])):
            try:
                observations.append(
                    RawDiscoveryObservation(
                        collector_id=collector_id,
                        collector_type=collector_type,
                        observed_at=item.get("observed_at", default_observed_at),
                        observation_type=ObservationType(item["observation_type"]),
                        source=item.get("source", collector_id),
                        raw_payload=item.get("payload", {}),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise DiscoveryFixtureError(f"Observación #{index} inválida en el fixture: {exc}") from exc
        return observations
