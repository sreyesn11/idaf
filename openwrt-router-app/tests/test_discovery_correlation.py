from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from discovery.correlation.identity_resolver import DeviceIdentityResolver
from discovery.enums import (
    CorrelationStatus,
    DeviceDiscoveryStatus,
    DeviceManagementStatus,
    DeviceType,
    IdentifierType,
)
from discovery.models import ExtractedIdentifier, NormalizedObservation
from discovery.enums import CollectorType, ObservationType
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository
from repositories.database import get_engine


@pytest.fixture()
def repos(tmp_path: Path):
    engine = get_engine(tmp_path / "history.db")
    devices = InventoryDeviceRepository(engine=engine)
    identifiers = DeviceIdentifierRepository(engine=engine)
    return devices, identifiers


@pytest.fixture()
def resolver(repos) -> DeviceIdentityResolver:
    devices, identifiers = repos
    return DeviceIdentityResolver(identifiers, devices)


def _observation(**identifiers: str) -> NormalizedObservation:
    extracted = []
    type_map = {
        "mac": IdentifierType.MAC,
        "agent_id": IdentifierType.AGENT_ID,
        "serial": IdentifierType.SERIAL,
        "thread_ext_address": IdentifierType.THREAD_EXT_ADDRESS,
        "hostname": IdentifierType.HOSTNAME,
        "ipv4": IdentifierType.IPV4,
        "ipv6": IdentifierType.IPV6,
    }
    confidence_map = {"ipv4": 0.5, "ipv6": 0.5, "hostname": 0.5}
    for key, value in identifiers.items():
        identifier_type = type_map[key]
        extracted.append(
            ExtractedIdentifier(
                identifier_type=identifier_type,
                value=value,
                normalized_value=value,
                confidence=confidence_map.get(key, 1.0),
            )
        )
    return NormalizedObservation(
        observation_type=ObservationType.DHCP_LEASE,
        collector_id="c1",
        collector_type=CollectorType.SIMULATED_ROUTER,
        source="test",
        observed_at=datetime.now().astimezone(),
        hostname=identifiers.get("hostname"),
        identifiers=extracted,
    )


def _seed_device(repos, seen_at: datetime | None = None, **identifiers: str) -> int:
    devices, identifier_repo = repos
    seen_at = seen_at or datetime.now().astimezone()
    record = devices.create(
        name="seed-device",
        alias="seed-device",
        device_type=DeviceType.IOT_NODE,
        management_status=DeviceManagementStatus.UNMANAGED,
        discovery_status=DeviceDiscoveryStatus.PENDING_APPROVAL,
        source="test",
        seen_at=seen_at,
    )
    type_map = {
        "mac": IdentifierType.MAC,
        "agent_id": IdentifierType.AGENT_ID,
        "thread_ext_address": IdentifierType.THREAD_EXT_ADDRESS,
        "hostname": IdentifierType.HOSTNAME,
        "ipv4": IdentifierType.IPV4,
    }
    for key, value in identifiers.items():
        identifier_repo.upsert(
            device_id=record.id,
            identifier_type=type_map[key],
            identifier_value=value,
            normalized_value=value,
            confidence=1.0,
            source="test",
            seen_at=seen_at,
        )
    return record.id


def test_new_device_when_nothing_matches(resolver: DeviceIdentityResolver) -> None:
    resolution = resolver.resolve(_observation(mac="aa:bb:cc:dd:ee:01"))
    assert resolution.status == CorrelationStatus.NEW_DEVICE


def test_insufficient_evidence_when_no_identifiers(resolver: DeviceIdentityResolver) -> None:
    observation = NormalizedObservation(
        observation_type=ObservationType.DHCP_LEASE,
        collector_id="c1",
        collector_type=CollectorType.SIMULATED_ROUTER,
        source="test",
        observed_at=datetime.now().astimezone(),
        identifiers=[],
    )
    resolution = resolver.resolve(observation)
    assert resolution.status == CorrelationStatus.INSUFFICIENT_EVIDENCE


def test_matches_by_same_agent_id(repos, resolver: DeviceIdentityResolver) -> None:
    device_id = _seed_device(repos, agent_id="idaf-agent-001")
    resolution = resolver.resolve(_observation(agent_id="idaf-agent-001"))
    assert resolution.status == CorrelationStatus.MATCHED_DEVICE
    assert resolution.resolved_device_id == device_id
    assert resolution.confidence >= 0.90


def test_matches_by_same_mac(repos, resolver: DeviceIdentityResolver) -> None:
    device_id = _seed_device(repos, mac="aa:bb:cc:dd:ee:02")
    resolution = resolver.resolve(_observation(mac="aa:bb:cc:dd:ee:02"))
    assert resolution.status == CorrelationStatus.MATCHED_DEVICE
    assert resolution.resolved_device_id == device_id


def test_matches_by_same_thread_ext_address(repos, resolver: DeviceIdentityResolver) -> None:
    device_id = _seed_device(repos, thread_ext_address="00:11:22:33:44:55:66:77")
    resolution = resolver.resolve(_observation(thread_ext_address="00:11:22:33:44:55:66:77"))
    assert resolution.status == CorrelationStatus.MATCHED_DEVICE
    assert resolution.resolved_device_id == device_id


def test_same_ip_alone_is_possible_duplicate_not_auto_matched(repos, resolver: DeviceIdentityResolver) -> None:
    """Spec 4.3: an IP alone must never auto-merge devices."""
    _seed_device(repos, ipv4="192.168.1.77")
    resolution = resolver.resolve(_observation(ipv4="192.168.1.77"))
    assert resolution.status == CorrelationStatus.POSSIBLE_DUPLICATE
    assert resolution.resolved_device_id is None


def test_shared_hostname_alone_is_weak_evidence(repos, resolver: DeviceIdentityResolver) -> None:
    _seed_device(repos, hostname="shared-host")
    resolution = resolver.resolve(_observation(hostname="shared-host"))
    assert resolution.status == CorrelationStatus.POSSIBLE_DUPLICATE


def test_mac_conflict_between_two_devices_is_identity_conflict(repos, resolver: DeviceIdentityResolver) -> None:
    _seed_device(repos, mac="aa:bb:cc:dd:ee:03")
    _seed_device(repos, agent_id="idaf-agent-999")
    # One observation whose MAC belongs to device A but whose agent_id
    # belongs to device B: strong identifiers disagree.
    observation = _observation(mac="aa:bb:cc:dd:ee:03", agent_id="idaf-agent-999")
    resolution = resolver.resolve(observation)
    assert resolution.status == CorrelationStatus.IDENTITY_CONFLICT


def test_manual_device_matched_by_later_observation(repos, resolver: DeviceIdentityResolver) -> None:
    """A manually-registered device (with a MAC) later shows up in a
    discovery observation with the same MAC — spec 8.3's "manual device
    detected afterwards" case."""
    device_id = _seed_device(repos, mac="aa:bb:cc:dd:ee:04", hostname="manual-device")
    resolution = resolver.resolve(_observation(mac="aa:bb:cc:dd:ee:04"))
    assert resolution.status == CorrelationStatus.MATCHED_DEVICE
    assert resolution.resolved_device_id == device_id
