from __future__ import annotations

from discovery.enums import CorrelationStatus, IdentifierType
from discovery.models import IdentityResolution, NormalizedObservation
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository

# Confidence formula (spec section 10.2): each identifier type contributes a
# base score when it matches an existing device's stored identifier. The
# resolution uses the *highest* score across all matched identifiers for a
# given candidate device. Kept as one flat table so the weighting is easy to
# audit and adjust without touching the resolution logic below.
#
#   >= 0.90            strong match  -> MATCHED_DEVICE
#   0.70 - 0.89         probable match -> MATCHED_DEVICE
#   0.40 - 0.69         possible duplicate -> POSSIBLE_DUPLICATE
#   <  0.40             insufficient evidence
IDENTIFIER_CONFIDENCE: dict[IdentifierType, float] = {
    IdentifierType.AGENT_ID: 0.95,
    IdentifierType.SERIAL: 0.95,
    IdentifierType.THREAD_EXT_ADDRESS: 0.93,
    IdentifierType.MAC: 0.90,
    IdentifierType.MDNS_NAME: 0.75,
    IdentifierType.HOSTNAME: 0.50,
    IdentifierType.RLOC16: 0.55,
    IdentifierType.IPV4: 0.50,
    IdentifierType.IPV6: 0.50,
}

# Hostname alone is a weak (0.50) signal per spec 10.1, but hostname +
# matching manufacturer is documented as a *medium* match — bump it here
# rather than conflating "hostname" as a single fixed-confidence type.
_HOSTNAME_WITH_MANUFACTURER_CONFIDENCE = 0.75

STRONG_MATCH_THRESHOLD = 0.90
MATCH_THRESHOLD = 0.70
POSSIBLE_DUPLICATE_THRESHOLD = 0.40

# Below this, a match is not trusted enough to even suggest a candidate device.
_STRONG_IDENTIFIER_TYPES = {
    IdentifierType.AGENT_ID,
    IdentifierType.SERIAL,
    IdentifierType.THREAD_EXT_ADDRESS,
    IdentifierType.MAC,
}


class DeviceIdentityResolver:
    """Decides whether a normalized observation belongs to a new device, an
    already-known device, or is ambiguous — never by IP alone (spec 4.3)."""

    def __init__(
        self,
        identifier_repository: DeviceIdentifierRepository,
        inventory_device_repository: InventoryDeviceRepository,
    ) -> None:
        self._identifiers = identifier_repository
        self._devices = inventory_device_repository

    def resolve(self, normalized: NormalizedObservation) -> IdentityResolution:
        if not normalized.identifiers:
            return IdentityResolution(
                status=CorrelationStatus.INSUFFICIENT_EVIDENCE,
                confidence=0.0,
                notes="La observación no produjo ningún identificador utilizable.",
            )

        # device_id -> {identifier_type: confidence}
        matches_by_device: dict[int, dict[IdentifierType, float]] = {}
        strong_devices_by_identifier: dict[IdentifierType, set[int]] = {}

        for identifier in normalized.identifiers:
            existing = self._identifiers.find_by_value(identifier.identifier_type, identifier.normalized_value)
            if existing is None:
                continue
            confidence = IDENTIFIER_CONFIDENCE.get(identifier.identifier_type, 0.4)
            if (
                identifier.identifier_type == IdentifierType.HOSTNAME
                and normalized.manufacturer_hint
                and self._manufacturer_matches(existing.device_id, normalized.manufacturer_hint)
            ):
                confidence = _HOSTNAME_WITH_MANUFACTURER_CONFIDENCE

            device_scores = matches_by_device.setdefault(existing.device_id, {})
            device_scores[identifier.identifier_type] = max(device_scores.get(identifier.identifier_type, 0.0), confidence)

            if identifier.identifier_type in _STRONG_IDENTIFIER_TYPES:
                strong_devices_by_identifier.setdefault(identifier.identifier_type, set()).add(existing.device_id)

        # A conflict is two *different* devices each strongly matched by a
        # different identifier within the same observation (e.g. this
        # observation's MAC belongs to device A but its agent_id belongs to
        # device B) — never a single identifier disagreeing with itself.
        all_strong_devices: set[int] = set()
        for devices in strong_devices_by_identifier.values():
            all_strong_devices |= devices
        if len(all_strong_devices) > 1:
            return IdentityResolution(
                status=CorrelationStatus.IDENTITY_CONFLICT,
                confidence=1.0,
                candidate_device_ids=sorted(all_strong_devices),
                matched_identifier_types=list(strong_devices_by_identifier.keys()),
                notes="Identificadores fuertes de esta observación apuntan a dispositivos distintos.",
            )

        if not matches_by_device:
            return IdentityResolution(
                status=CorrelationStatus.NEW_DEVICE,
                confidence=0.0,
                notes="Ningún identificador coincide con dispositivos existentes.",
            )

        best_device_id, best_score, best_types = self._best_candidate(matches_by_device)

        if best_score >= MATCH_THRESHOLD:
            return IdentityResolution(
                status=CorrelationStatus.MATCHED_DEVICE,
                confidence=best_score,
                resolved_device_id=best_device_id,
                matched_identifier_types=best_types,
            )
        if best_score >= POSSIBLE_DUPLICATE_THRESHOLD:
            return IdentityResolution(
                status=CorrelationStatus.POSSIBLE_DUPLICATE,
                confidence=best_score,
                candidate_device_ids=[best_device_id],
                matched_identifier_types=best_types,
                notes="Coincidencia débil (IP/hostname): requiere revisión manual antes de fusionar.",
            )
        return IdentityResolution(
            status=CorrelationStatus.NEW_DEVICE,
            confidence=best_score,
            notes="La evidencia encontrada es demasiado débil para asociarla automáticamente.",
        )

    @staticmethod
    def _best_candidate(
        matches_by_device: dict[int, dict[IdentifierType, float]],
    ) -> tuple[int, float, list[IdentifierType]]:
        best_device_id = -1
        best_score = -1.0
        best_types: list[IdentifierType] = []
        for device_id, scores in matches_by_device.items():
            device_best = max(scores.values())
            if device_best > best_score:
                best_score = device_best
                best_device_id = device_id
                best_types = list(scores.keys())
        return best_device_id, best_score, best_types

    def _manufacturer_matches(self, device_id: int, manufacturer_hint: str) -> bool:
        device = self._devices.get_by_id(device_id)
        if device is None or not device.manufacturer:
            return False
        return device.manufacturer.strip().lower() == manufacturer_hint.strip().lower()
