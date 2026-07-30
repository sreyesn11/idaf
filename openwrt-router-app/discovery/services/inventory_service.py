from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from discovery.correlation.duplicate_detector import DuplicateCandidate, DuplicateDetector
from discovery.enums import CorrelationStatus, DeviceDiscoveryStatus
from discovery.repositories.address_repository import DeviceAddressRepository
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.interface_repository import DeviceInterfaceRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRecord, InventoryDeviceRepository
from discovery.repositories.observation_repository import DiscoveryObservationRecord, DiscoveryObservationRepository
from repositories.database import naive

DEFAULT_STALE_AFTER = timedelta(days=7)


class InventoryService:
    """Read/aggregation side of the inventory — everything the Streamlit
    'Descubrimiento' page needs to render its Resumen/Inventario/Pendientes/
    Conflictos tabs, plus the periodic stale-marking sweep."""

    def __init__(
        self,
        inventory_device_repository: InventoryDeviceRepository,
        identifier_repository: DeviceIdentifierRepository,
        address_repository: DeviceAddressRepository,
        interface_repository: DeviceInterfaceRepository,
        observation_repository: DiscoveryObservationRepository,
    ) -> None:
        self._devices = inventory_device_repository
        self._identifiers = identifier_repository
        self._addresses = address_repository
        self._interfaces = interface_repository
        self._observations = observation_repository
        self._duplicate_detector = DuplicateDetector(inventory_device_repository, identifier_repository)

    def summary(self) -> dict[str, Any]:
        device_stats = self._devices.stats()
        return {
            "total": device_stats["total"],
            "by_status": device_stats["by_status"],
            "pending_approval": device_stats["by_status"].get(DeviceDiscoveryStatus.PENDING_APPROVAL.value, 0),
            "approved": device_stats["by_status"].get(DeviceDiscoveryStatus.APPROVED.value, 0),
            "ignored": device_stats["by_status"].get(DeviceDiscoveryStatus.IGNORED.value, 0),
            "stale": device_stats["by_status"].get(DeviceDiscoveryStatus.STALE.value, 0),
            "observations_total": self._observations.stats()["total"],
            "identity_conflicts": len(
                self._observations.list_by_correlation_status(CorrelationStatus.IDENTITY_CONFLICT)
            ),
            "possible_duplicate_pairs": len(self._duplicate_detector.find_candidate_duplicate_pairs()),
        }

    def list_pending(self) -> list[InventoryDeviceRecord]:
        return self._devices.list_all(discovery_status=DeviceDiscoveryStatus.PENDING_APPROVAL)

    def list_approved(self) -> list[InventoryDeviceRecord]:
        return self._devices.list_all(discovery_status=DeviceDiscoveryStatus.APPROVED)

    def list_ignored(self) -> list[InventoryDeviceRecord]:
        return self._devices.list_all(discovery_status=DeviceDiscoveryStatus.IGNORED)

    def list_stale(self) -> list[InventoryDeviceRecord]:
        return self._devices.list_all(discovery_status=DeviceDiscoveryStatus.STALE)

    def list_all(self) -> list[InventoryDeviceRecord]:
        return self._devices.list_all()

    def list_identity_conflicts(self) -> list[DiscoveryObservationRecord]:
        return self._observations.list_by_correlation_status(CorrelationStatus.IDENTITY_CONFLICT)

    def list_possible_duplicates(self) -> list[DuplicateCandidate]:
        return self._duplicate_detector.find_candidate_duplicate_pairs()

    def device_detail(self, device_id: int) -> dict[str, Any] | None:
        device = self._devices.get_by_id(device_id)
        if device is None:
            return None
        return {
            "device": device,
            "identifiers": self._identifiers.list_for_device(device_id),
            "addresses": self._addresses.list_for_device(device_id),
            "interfaces": self._interfaces.list_for_device(device_id),
            "observations": self._observations.list_for_device(device_id),
        }

    def mark_stale(self, older_than: timedelta = DEFAULT_STALE_AFTER, now: datetime | None = None) -> int:
        """Flags devices that haven't been re-observed in a while as STALE
        (spec: a device that "deja de aparecer"). Only APPROVED/PENDING
        devices are eligible — IGNORED/REMOVED/STALE are left alone."""
        reference = now or datetime.now().astimezone()
        cutoff = naive(reference - older_than)
        changed = 0
        for status in (DeviceDiscoveryStatus.APPROVED, DeviceDiscoveryStatus.PENDING_APPROVAL):
            for device in self._devices.list_all(discovery_status=status):
                if naive(device.last_seen_at) < cutoff:
                    self._devices.update_status(device.id, discovery_status=DeviceDiscoveryStatus.STALE)
                    changed += 1
        return changed
