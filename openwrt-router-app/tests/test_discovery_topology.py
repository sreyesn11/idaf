from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from diagnostics.enums import DiagnosticState
from discovery.enums import DeviceDiscoveryStatus, DeviceManagementStatus, DeviceType, LinkType
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository
from discovery.repositories.topology_link_repository import TopologyLinkRepository
from repositories.database import get_engine
from topology.builder import build_inventory_topology


@pytest.fixture()
def engine(tmp_path: Path):
    return get_engine(tmp_path / "history.db")


@pytest.fixture()
def device_repo(engine) -> InventoryDeviceRepository:
    return InventoryDeviceRepository(engine=engine)


@pytest.fixture()
def link_repo(engine) -> TopologyLinkRepository:
    return TopologyLinkRepository(engine=engine)


def _make_device(device_repo: InventoryDeviceRepository, status: DeviceDiscoveryStatus, name: str = "gw1"):
    return device_repo.create(
        name=name,
        alias=name,
        device_type=DeviceType.GATEWAY,
        management_status=DeviceManagementStatus.UNMANAGED,
        discovery_status=status,
        source="test",
        seen_at=datetime.now().astimezone(),
    )


def test_upsert_creates_link(device_repo: InventoryDeviceRepository, link_repo: TopologyLinkRepository) -> None:
    parent = _make_device(device_repo, DeviceDiscoveryStatus.APPROVED, "parent")
    child = _make_device(device_repo, DeviceDiscoveryStatus.APPROVED, "child")
    link_repo.upsert(
        source_device_id=parent.id, target_device_id=child.id, link_type=LinkType.WIFI,
        seen_at=datetime.now().astimezone(),
    )
    links = link_repo.list_all()
    assert len(links) == 1
    assert links[0].source_device_id == parent.id
    assert links[0].target_device_id == child.id


def test_upsert_same_edge_twice_does_not_duplicate(
    device_repo: InventoryDeviceRepository, link_repo: TopologyLinkRepository
) -> None:
    parent = _make_device(device_repo, DeviceDiscoveryStatus.APPROVED, "parent")
    child = _make_device(device_repo, DeviceDiscoveryStatus.APPROVED, "child")
    now = datetime.now().astimezone()
    link_repo.upsert(source_device_id=parent.id, target_device_id=child.id, link_type=LinkType.WIFI, seen_at=now)
    link_repo.upsert(source_device_id=parent.id, target_device_id=child.id, link_type=LinkType.WIFI, seen_at=now)
    assert len(link_repo.list_all()) == 1


def test_upsert_refreshes_last_seen(device_repo: InventoryDeviceRepository, link_repo: TopologyLinkRepository) -> None:
    from datetime import timedelta

    parent = _make_device(device_repo, DeviceDiscoveryStatus.APPROVED, "parent")
    child = _make_device(device_repo, DeviceDiscoveryStatus.APPROVED, "child")
    first_seen = datetime.now().astimezone()
    later = first_seen + timedelta(minutes=10)
    link_repo.upsert(source_device_id=parent.id, target_device_id=child.id, link_type=LinkType.THREAD, seen_at=first_seen)
    link_repo.upsert(source_device_id=parent.id, target_device_id=child.id, link_type=LinkType.THREAD, seen_at=later)
    link = link_repo.list_all()[0]
    assert link.last_seen_at.replace(tzinfo=None) == later.replace(tzinfo=None)


def test_build_inventory_topology_includes_approved_devices(
    device_repo: InventoryDeviceRepository, link_repo: TopologyLinkRepository
) -> None:
    approved = _make_device(device_repo, DeviceDiscoveryStatus.APPROVED, "approved-device")
    graph = build_inventory_topology([approved], [], include_pending=True)
    assert len(graph.nodes) == 1
    assert graph.nodes[0].state == DiagnosticState.HEALTHY


def test_build_inventory_topology_excludes_ignored_devices(
    device_repo: InventoryDeviceRepository,
) -> None:
    ignored = _make_device(device_repo, DeviceDiscoveryStatus.IGNORED, "ignored-device")
    graph = build_inventory_topology([ignored], [], include_pending=True)
    assert graph.nodes == []


def test_build_inventory_topology_can_exclude_pending(device_repo: InventoryDeviceRepository) -> None:
    pending = _make_device(device_repo, DeviceDiscoveryStatus.PENDING_APPROVAL, "pending-device")
    graph_with_pending = build_inventory_topology([pending], [], include_pending=True)
    graph_without_pending = build_inventory_topology([pending], [], include_pending=False)
    assert len(graph_with_pending.nodes) == 1
    assert len(graph_without_pending.nodes) == 0


def test_build_inventory_topology_link_requires_both_endpoints_visible(
    device_repo: InventoryDeviceRepository, link_repo: TopologyLinkRepository
) -> None:
    parent = _make_device(device_repo, DeviceDiscoveryStatus.APPROVED, "parent")
    child = _make_device(device_repo, DeviceDiscoveryStatus.IGNORED, "child")
    link_repo.upsert(
        source_device_id=parent.id, target_device_id=child.id, link_type=LinkType.WIFI,
        seen_at=datetime.now().astimezone(),
    )
    graph = build_inventory_topology([parent, child], link_repo.list_all(), include_pending=True)
    # Child is IGNORED, so it (and therefore the link to it) never renders.
    assert len(graph.nodes) == 1
    assert graph.links == []
