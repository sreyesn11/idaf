from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from discovery.correlation.merge_planner import MergePlanner
from discovery.enums import (
    AddressFamily,
    AddressScope,
    CollectorType,
    CorrelationStatus,
    DeviceDiscoveryStatus,
    DeviceManagementStatus,
    DeviceType,
    IdentifierType,
    ObservationType,
)
from discovery.repositories.address_repository import DeviceAddressRepository
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository
from discovery.repositories.observation_repository import DiscoveryObservationRepository
from repositories.database import get_engine


@pytest.fixture()
def engine(tmp_path: Path):
    return get_engine(tmp_path / "history.db")


@pytest.fixture()
def device_repo(engine) -> InventoryDeviceRepository:
    return InventoryDeviceRepository(engine=engine)


@pytest.fixture()
def identifier_repo(engine) -> DeviceIdentifierRepository:
    return DeviceIdentifierRepository(engine=engine)


@pytest.fixture()
def address_repo(engine) -> DeviceAddressRepository:
    return DeviceAddressRepository(engine=engine)


@pytest.fixture()
def observation_repo(engine) -> DiscoveryObservationRepository:
    return DiscoveryObservationRepository(engine=engine)


def _create_device(device_repo: InventoryDeviceRepository, **overrides):
    defaults = dict(
        name="test-device",
        alias="test-device",
        device_type=DeviceType.IOT_NODE,
        management_status=DeviceManagementStatus.UNMANAGED,
        discovery_status=DeviceDiscoveryStatus.PENDING_APPROVAL,
        source="test",
        seen_at=datetime.now().astimezone(),
    )
    defaults.update(overrides)
    return device_repo.create(**defaults)


def test_create_device(device_repo: InventoryDeviceRepository) -> None:
    record = _create_device(device_repo)
    assert record.id is not None
    assert record.discovery_status == DeviceDiscoveryStatus.PENDING_APPROVAL.value


def test_touch_last_seen_only_moves_forward(device_repo: InventoryDeviceRepository) -> None:
    early = datetime(2026, 1, 1, tzinfo=None).astimezone()
    late = datetime(2026, 6, 1, tzinfo=None).astimezone()
    record = _create_device(device_repo, seen_at=early)

    device_repo.touch_last_seen(record.id, late)
    updated = device_repo.get_by_id(record.id)
    assert updated.last_seen_at.replace(tzinfo=None) == late.replace(tzinfo=None)

    # An older timestamp must never move last_seen_at backwards.
    device_repo.touch_last_seen(record.id, early)
    unchanged = device_repo.get_by_id(record.id)
    assert unchanged.last_seen_at.replace(tzinfo=None) == late.replace(tzinfo=None)


def test_save_observation(observation_repo: DiscoveryObservationRepository) -> None:
    record = observation_repo.save(
        collector_id="c1",
        collector_type=CollectorType.SIMULATED_ROUTER,
        observed_at=datetime.now().astimezone(),
        observation_type=ObservationType.DHCP_LEASE,
        source="test",
        raw_payload_json="{}",
        normalized_payload_json="{}",
        confidence=0.9,
        correlation_status=CorrelationStatus.NEW_DEVICE,
        resolved_device_id=None,
    )
    assert record.id is not None
    assert observation_repo.stats()["total"] == 1


def test_save_and_upsert_identifier_avoids_duplicate_rows(
    device_repo: InventoryDeviceRepository, identifier_repo: DeviceIdentifierRepository
) -> None:
    record = _create_device(device_repo)
    now = datetime.now().astimezone()
    identifier_repo.upsert(
        device_id=record.id,
        identifier_type=IdentifierType.MAC,
        identifier_value="AA:BB:CC:DD:EE:FF",
        normalized_value="aa:bb:cc:dd:ee:ff",
        confidence=1.0,
        source="test",
        seen_at=now,
    )
    identifier_repo.upsert(
        device_id=record.id,
        identifier_type=IdentifierType.MAC,
        identifier_value="AA:BB:CC:DD:EE:FF",
        normalized_value="aa:bb:cc:dd:ee:ff",
        confidence=1.0,
        source="test",
        seen_at=now + timedelta(minutes=5),
    )
    assert len(identifier_repo.list_for_device(record.id)) == 1


def test_find_by_value_locates_the_owning_device(
    device_repo: InventoryDeviceRepository, identifier_repo: DeviceIdentifierRepository
) -> None:
    record = _create_device(device_repo)
    identifier_repo.upsert(
        device_id=record.id,
        identifier_type=IdentifierType.MAC,
        identifier_value="AA:BB:CC:DD:EE:01",
        normalized_value="aa:bb:cc:dd:ee:01",
        confidence=1.0,
        source="test",
        seen_at=datetime.now().astimezone(),
    )
    found = identifier_repo.find_by_value(IdentifierType.MAC, "aa:bb:cc:dd:ee:01")
    assert found is not None
    assert found.device_id == record.id
    assert identifier_repo.find_by_value(IdentifierType.MAC, "aa:bb:cc:dd:ee:99") is None


def test_ipv4_address_upsert_marks_previous_as_not_current(
    device_repo: InventoryDeviceRepository, address_repo: DeviceAddressRepository
) -> None:
    record = _create_device(device_repo)
    now = datetime.now().astimezone()
    address_repo.upsert(
        device_id=record.id, address="192.168.1.10", address_family=AddressFamily.IPV4,
        scope=AddressScope.GLOBAL, source="test", seen_at=now,
    )
    address_repo.upsert(
        device_id=record.id, address="192.168.1.11", address_family=AddressFamily.IPV4,
        scope=AddressScope.GLOBAL, source="test", seen_at=now + timedelta(minutes=5),
    )
    addresses = {a.address: a.is_current for a in address_repo.list_for_device(record.id)}
    assert addresses == {"192.168.1.10": False, "192.168.1.11": True}


def test_multiple_ipv6_addresses_stay_current_simultaneously(
    device_repo: InventoryDeviceRepository, address_repo: DeviceAddressRepository
) -> None:
    record = _create_device(device_repo)
    now = datetime.now().astimezone()
    for addr in ["fd00:1daf::1", "fd00:1daf::2", "fe80::1"]:
        address_repo.upsert(
            device_id=record.id, address=addr, address_family=AddressFamily.IPV6,
            scope=AddressScope.GLOBAL, source="test", seen_at=now,
        )
    addresses = address_repo.list_for_device(record.id)
    assert len(addresses) == 3
    assert all(a.is_current for a in addresses)


class TestMergeTransaction:
    def test_merge_moves_identifiers_and_marks_source_removed(
        self, engine, device_repo: InventoryDeviceRepository, identifier_repo: DeviceIdentifierRepository
    ) -> None:
        source = _create_device(device_repo, name="dup-a", alias="dup-a")
        target = _create_device(device_repo, name="dup-b", alias="dup-b")
        identifier_repo.upsert(
            device_id=source.id, identifier_type=IdentifierType.MAC, identifier_value="AA:BB:CC:DD:EE:05",
            normalized_value="aa:bb:cc:dd:ee:05", confidence=1.0, source="test", seen_at=datetime.now().astimezone(),
        )

        planner = MergePlanner(engine=engine)
        planner.merge(source.id, target.id, confirmed=True)

        assert identifier_repo.list_for_device(target.id)[0].normalized_value == "aa:bb:cc:dd:ee:05"
        assert identifier_repo.list_for_device(source.id) == []
        merged_source = device_repo.get_by_id(source.id)
        assert merged_source.discovery_status == DeviceDiscoveryStatus.REMOVED.value

    def test_merge_requires_confirmation(self, engine, device_repo: InventoryDeviceRepository) -> None:
        from core.exceptions import InvalidMergeError

        source = _create_device(device_repo)
        target = _create_device(device_repo)
        planner = MergePlanner(engine=engine)
        with pytest.raises(InvalidMergeError):
            planner.merge(source.id, target.id, confirmed=False)

    def test_merge_rolls_back_on_failure(
        self, engine, device_repo: InventoryDeviceRepository, identifier_repo: DeviceIdentifierRepository
    ) -> None:
        """If the merge blows up partway through, nothing should be moved —
        not even the identifiers that would have been reassigned before the
        failing step."""
        from core.exceptions import InvalidMergeError

        source = _create_device(device_repo, name="dup-a", alias="dup-a")
        identifier_repo.upsert(
            device_id=source.id, identifier_type=IdentifierType.MAC, identifier_value="AA:BB:CC:DD:EE:06",
            normalized_value="aa:bb:cc:dd:ee:06", confidence=1.0, source="test", seen_at=datetime.now().astimezone(),
        )

        planner = MergePlanner(engine=engine)
        # Target device_id 9999 does not exist -> _validate raises inside the
        # transaction, after identifiers would otherwise have been queued.
        with pytest.raises(InvalidMergeError):
            planner.merge(source.id, 9999, confirmed=True)

        # The source's identifier must still be exactly where it started.
        assert len(identifier_repo.list_for_device(source.id)) == 1
        untouched_source = device_repo.get_by_id(source.id)
        assert untouched_source.discovery_status != DeviceDiscoveryStatus.REMOVED.value
