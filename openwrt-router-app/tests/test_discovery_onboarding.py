from __future__ import annotations

from pathlib import Path

import pytest

from core.exceptions import DiscoveryFixtureError
from discovery.collectors.simulated import SimulatedDiscoveryCollector
from discovery.correlation.merge_planner import MergePlanner
from discovery.enums import DeviceDiscoveryStatus, DeviceManagementStatus, DeviceType
from discovery.repositories.address_repository import DeviceAddressRepository
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.interface_repository import DeviceInterfaceRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository
from discovery.repositories.observation_repository import DiscoveryObservationRepository
from discovery.repositories.topology_link_repository import TopologyLinkRepository
from discovery.services.discovery_service import DiscoveryService
from discovery.services.inventory_service import InventoryService
from discovery.services.onboarding_service import OnboardingService
from repositories.database import get_engine

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "discovery" / "collectors" / "fixtures" / "lab_network.json"


@pytest.fixture()
def engine(tmp_path: Path):
    return get_engine(tmp_path / "history.db")


@pytest.fixture()
def discovery_service(engine, tmp_path: Path) -> DiscoveryService:
    return DiscoveryService(
        InventoryDeviceRepository(engine=engine),
        DeviceIdentifierRepository(engine=engine),
        DeviceAddressRepository(engine=engine),
        DeviceInterfaceRepository(engine=engine),
        DiscoveryObservationRepository(engine=engine),
        TopologyLinkRepository(engine=engine),
        evidence_dir=tmp_path / "evidence",
    )


@pytest.fixture()
def inventory_service(engine) -> InventoryService:
    return InventoryService(
        InventoryDeviceRepository(engine=engine),
        DeviceIdentifierRepository(engine=engine),
        DeviceAddressRepository(engine=engine),
        DeviceInterfaceRepository(engine=engine),
        DiscoveryObservationRepository(engine=engine),
    )


@pytest.fixture()
def onboarding_service(engine) -> OnboardingService:
    return OnboardingService(InventoryDeviceRepository(engine=engine), MergePlanner(engine=engine))


class TestDiscoveryServiceRun:
    def test_run_creates_pending_devices_from_fixture(self, discovery_service: DiscoveryService) -> None:
        evidence = discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        assert evidence.devices_created > 0
        assert not evidence.errors

    def test_run_is_idempotent_on_second_pass(self, discovery_service: DiscoveryService, engine) -> None:
        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        first_total = len(InventoryDeviceRepository(engine=engine).list_all())

        second_evidence = discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        second_total = len(InventoryDeviceRepository(engine=engine).list_all())

        assert second_evidence.devices_created == 0
        assert second_total == first_total

    def test_run_writes_evidence_file(self, discovery_service: DiscoveryService, tmp_path: Path) -> None:
        evidence = discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        matches = list((tmp_path / "evidence").rglob(f"{evidence.execution_id}.json"))
        assert len(matches) == 1

    def test_run_handles_missing_fixture_without_crashing(self, discovery_service: DiscoveryService) -> None:
        missing = SimulatedDiscoveryCollector(Path("does-not-exist.json"))
        evidence = discovery_service.run(missing, fixture_name="does-not-exist.json")
        assert evidence.errors
        assert evidence.devices_created == 0

    def test_devices_start_pending_never_managed(self, discovery_service: DiscoveryService, engine) -> None:
        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        devices = InventoryDeviceRepository(engine=engine).list_all()
        assert devices
        assert all(d.discovery_status == DeviceDiscoveryStatus.PENDING_APPROVAL.value for d in devices)
        assert all(d.management_status == DeviceManagementStatus.UNMANAGED.value for d in devices)

    def test_parent_child_topology_links_created(self, discovery_service: DiscoveryService, engine) -> None:
        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        links = TopologyLinkRepository(engine=engine).list_all()
        assert len(links) >= 4  # gw1->esp32-01, gw1->esp32-02, gw2->esp32-03, gw2->monitor-luz


class TestOnboardingFlow:
    def _first_pending_id(self, engine) -> int:
        pending = InventoryDeviceRepository(engine=engine).list_all(discovery_status=DeviceDiscoveryStatus.PENDING_APPROVAL)
        return pending[0].id

    def test_approve_moves_to_approved(
        self, discovery_service: DiscoveryService, onboarding_service: OnboardingService, engine
    ) -> None:
        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        device_id = self._first_pending_id(engine)

        approved = onboarding_service.approve(device_id)
        assert approved.discovery_status == DeviceDiscoveryStatus.APPROVED.value
        assert approved.approved_at is not None

    def test_ignore_then_restore(
        self, discovery_service: DiscoveryService, onboarding_service: OnboardingService, engine
    ) -> None:
        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        device_id = self._first_pending_id(engine)

        ignored = onboarding_service.ignore(device_id)
        assert ignored.discovery_status == DeviceDiscoveryStatus.IGNORED.value

        restored = onboarding_service.restore(device_id)
        assert restored.discovery_status == DeviceDiscoveryStatus.PENDING_APPROVAL.value

    def test_edit_and_approve_updates_fields(
        self, discovery_service: DiscoveryService, onboarding_service: OnboardingService, engine
    ) -> None:
        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        device_id = self._first_pending_id(engine)

        updated = onboarding_service.edit_and_approve(
            device_id, name="Renamed", alias="renamed", device_type=DeviceType.SENSOR
        )
        assert updated.name == "Renamed"
        assert updated.device_type == DeviceType.SENSOR.value
        assert updated.discovery_status == DeviceDiscoveryStatus.APPROVED.value

    def test_merge_via_onboarding_service(
        self, discovery_service: DiscoveryService, onboarding_service: OnboardingService, engine
    ) -> None:
        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        devices = InventoryDeviceRepository(engine=engine).list_all()
        source, target = devices[0], devices[1]

        preview = onboarding_service.preview_merge(source.id, target.id)
        assert preview.source_device_id == source.id

        onboarding_service.merge(source.id, target.id, confirmed=True)
        merged_source = InventoryDeviceRepository(engine=engine).get_by_id(source.id)
        assert merged_source.discovery_status == DeviceDiscoveryStatus.REMOVED.value


class TestInventoryServiceSummary:
    def test_summary_counts_match_after_discovery(
        self, discovery_service: DiscoveryService, inventory_service: InventoryService
    ) -> None:
        evidence = discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        summary = inventory_service.summary()
        assert summary["total"] == evidence.devices_created
        assert summary["pending_approval"] == evidence.devices_created

    def test_mark_stale_flags_old_devices(
        self, discovery_service: DiscoveryService, inventory_service: InventoryService, engine
    ) -> None:
        from datetime import timedelta

        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        changed = inventory_service.mark_stale(older_than=timedelta(seconds=-1))  # everything is "older" than now+1s
        assert changed > 0
        stale = InventoryDeviceRepository(engine=engine).list_all(discovery_status=DeviceDiscoveryStatus.STALE)
        assert len(stale) == changed

    def test_mark_stale_leaves_recent_devices_alone(
        self, discovery_service: DiscoveryService, inventory_service: InventoryService
    ) -> None:
        from datetime import timedelta

        discovery_service.run(SimulatedDiscoveryCollector(FIXTURE_PATH), fixture_name=FIXTURE_PATH.name)
        changed = inventory_service.mark_stale(older_than=timedelta(days=7))
        assert changed == 0
