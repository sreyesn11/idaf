from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core.exceptions import DiscoveryFixtureError
from discovery.collectors.simulated import SimulatedDiscoveryCollector, list_available_fixtures
from discovery.correlation.duplicate_detector import DuplicateDetector
from discovery.enums import DeviceDiscoveryStatus, DeviceManagementStatus, DeviceType, IdentifierType
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository
from repositories.database import get_engine

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "discovery" / "collectors" / "fixtures" / "lab_network.json"


def test_list_available_fixtures_finds_lab_network() -> None:
    fixtures = list_available_fixtures()
    assert any(f.name == "lab_network.json" for f in fixtures)


def test_collect_parses_all_observations() -> None:
    collector = SimulatedDiscoveryCollector(FIXTURE_PATH)
    observations = collector.collect()
    assert len(observations) == 20
    assert all(o.collector_id == "collector-lab-network" for o in observations)


def test_collect_raises_friendly_error_for_missing_file(tmp_path: Path) -> None:
    collector = SimulatedDiscoveryCollector(tmp_path / "missing.json")
    with pytest.raises(DiscoveryFixtureError):
        collector.collect()


def test_collect_raises_friendly_error_for_malformed_json(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    collector = SimulatedDiscoveryCollector(bad_file)
    with pytest.raises(DiscoveryFixtureError):
        collector.collect()


def test_collect_raises_friendly_error_for_missing_required_keys(tmp_path: Path) -> None:
    bad_file = tmp_path / "incomplete.json"
    bad_file.write_text('{"observations": []}', encoding="utf-8")
    collector = SimulatedDiscoveryCollector(bad_file)
    with pytest.raises(DiscoveryFixtureError):
        collector.collect()


@pytest.fixture()
def repos(tmp_path: Path):
    engine = get_engine(tmp_path / "history.db")
    devices = InventoryDeviceRepository(engine=engine)
    identifiers = DeviceIdentifierRepository(engine=engine)
    return devices, identifiers


def _seeded_device(devices, identifiers, name: str, mac: str):
    record = devices.create(
        name=name,
        alias=name,
        device_type=DeviceType.IOT_NODE,
        management_status=DeviceManagementStatus.UNMANAGED,
        discovery_status=DeviceDiscoveryStatus.PENDING_APPROVAL,
        source="test",
        seen_at=datetime.now().astimezone(),
    )
    identifiers.upsert(
        device_id=record.id,
        identifier_type=IdentifierType.MAC,
        identifier_value=mac,
        normalized_value=mac,
        confidence=1.0,
        source="test",
        seen_at=datetime.now().astimezone(),
    )
    return record


def test_duplicate_detector_finds_devices_sharing_an_identifier(repos) -> None:
    devices, identifiers = repos
    device_a = _seeded_device(devices, identifiers, "device-a", "aa:bb:cc:dd:ee:10")
    device_b = _seeded_device(devices, identifiers, "device-b", "aa:bb:cc:dd:ee:11")
    # Deliberately give device_b the *same* MAC as device_a too (as if two
    # separate pending rows were created for what's really one physical
    # device) — this is the case the detector exists to catch.
    identifiers.upsert(
        device_id=device_b.id,
        identifier_type=IdentifierType.MAC,
        identifier_value="aa:bb:cc:dd:ee:10",
        normalized_value="aa:bb:cc:dd:ee:10",
        confidence=1.0,
        source="test",
        seen_at=datetime.now().astimezone(),
    )

    detector = DuplicateDetector(devices, identifiers)
    candidates = detector.find_candidate_duplicate_pairs()
    assert len(candidates) == 1
    assert {candidates[0].device_a_id, candidates[0].device_b_id} == {device_a.id, device_b.id}


def test_duplicate_detector_finds_nothing_when_devices_are_distinct(repos) -> None:
    devices, identifiers = repos
    _seeded_device(devices, identifiers, "device-a", "aa:bb:cc:dd:ee:20")
    _seeded_device(devices, identifiers, "device-b", "aa:bb:cc:dd:ee:21")

    detector = DuplicateDetector(devices, identifiers)
    assert detector.find_candidate_duplicate_pairs() == []
