from __future__ import annotations

from dataclasses import dataclass

from discovery.correlation.identity_resolver import IDENTIFIER_CONFIDENCE
from discovery.enums import IdentifierType
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRecord, InventoryDeviceRepository


@dataclass(frozen=True)
class DuplicateCandidate:
    device_a_id: int
    device_b_id: int
    shared_identifier_types: list[IdentifierType]
    confidence: float


class DuplicateDetector:
    """Finds devices that already exist as *separate* inventory rows but
    share an identifier — the case `DeviceIdentityResolver` can't catch by
    itself, since it only ever looks at one incoming observation at a time.

    This runs across the whole inventory (e.g. from the 'Conflictos y
    duplicados' page), not per observation.
    """

    def __init__(
        self,
        inventory_device_repository: InventoryDeviceRepository,
        identifier_repository: DeviceIdentifierRepository,
    ) -> None:
        self._devices = inventory_device_repository
        self._identifiers = identifier_repository

    def find_candidate_duplicate_pairs(self) -> list[DuplicateCandidate]:
        devices: list[InventoryDeviceRecord] = self._devices.list_all()
        identifiers_by_device = {device.id: self._identifiers.list_for_device(device.id) for device in devices}

        pairs: dict[tuple[int, int], dict[IdentifierType, float]] = {}
        device_ids = list(identifiers_by_device.keys())
        for i, device_a_id in enumerate(device_ids):
            for device_b_id in device_ids[i + 1 :]:
                shared = self._shared_identifier_types(
                    identifiers_by_device[device_a_id], identifiers_by_device[device_b_id]
                )
                if shared:
                    pairs[(device_a_id, device_b_id)] = shared

        candidates = [
            DuplicateCandidate(
                device_a_id=device_a_id,
                device_b_id=device_b_id,
                shared_identifier_types=list(shared.keys()),
                confidence=max(shared.values()),
            )
            for (device_a_id, device_b_id), shared in pairs.items()
        ]
        return sorted(candidates, key=lambda c: c.confidence, reverse=True)

    @staticmethod
    def _shared_identifier_types(identifiers_a, identifiers_b) -> dict[IdentifierType, float]:
        values_a = {(record.identifier_type, record.normalized_value) for record in identifiers_a}
        shared: dict[IdentifierType, float] = {}
        for record in identifiers_b:
            key = (record.identifier_type, record.normalized_value)
            if key in values_a:
                identifier_type = IdentifierType(record.identifier_type)
                shared[identifier_type] = IDENTIFIER_CONFIDENCE.get(identifier_type, 0.4)
        return shared
