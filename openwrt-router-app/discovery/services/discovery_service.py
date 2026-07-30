from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from core.constants import DISCOVERY_EVIDENCE_DIR
from core.exceptions import DiscoveryFixtureError
from discovery.collectors.base import DiscoveryCollector
from discovery.correlation.identity_resolver import DeviceIdentityResolver
from discovery.enums import (
    CorrelationStatus,
    DeviceDiscoveryStatus,
    DeviceManagementStatus,
    DeviceType,
    IdentifierType,
    LinkType,
    ObservationType,
)
from discovery.models import DiscoveryRunEvidence, DiscoveryRunResultItem, NormalizedObservation
from discovery.normalization.normalizer import normalize_observation
from discovery.repositories.address_repository import DeviceAddressRepository
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.interface_repository import DeviceInterfaceRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository
from discovery.repositories.observation_repository import DiscoveryObservationRepository
from discovery.repositories.topology_link_repository import TopologyLinkRepository

logger = logging.getLogger(__name__)

# Observation types whose source clearly identifies a wired/wireless
# interface worth recording on the device (spec section 5.3). Kept narrow —
# Thread reports don't carry a MAC-based interface in this fixture format.
_INTERFACE_OBSERVATION_TYPES = {
    ObservationType.WIFI_CLIENT: "wifi",
    ObservationType.GATEWAY_REPORT: "ethernet",
    ObservationType.DHCP_LEASE: "ethernet",
}

_LINK_TYPE_BY_OBSERVATION = {
    ObservationType.THREAD_NODE_REPORT: "THREAD",
    ObservationType.WIFI_CLIENT: "WIFI",
}


class DiscoveryService:
    """Orchestrates one discovery run: collect -> normalize -> resolve
    identity -> persist devices/identifiers/addresses/links -> write
    evidence. Every step after `collect()` is collector-agnostic, so a real
    collector can replace `SimulatedDiscoveryCollector` without touching
    this class (spec section 2).
    """

    def __init__(
        self,
        inventory_device_repository: InventoryDeviceRepository,
        identifier_repository: DeviceIdentifierRepository,
        address_repository: DeviceAddressRepository,
        interface_repository: DeviceInterfaceRepository,
        observation_repository: DiscoveryObservationRepository,
        topology_link_repository: TopologyLinkRepository,
        resolver: DeviceIdentityResolver | None = None,
        evidence_dir: Path = DISCOVERY_EVIDENCE_DIR,
    ) -> None:
        self._devices = inventory_device_repository
        self._identifiers = identifier_repository
        self._addresses = address_repository
        self._interfaces = interface_repository
        self._observations = observation_repository
        self._topology_links = topology_link_repository
        self._resolver = resolver or DeviceIdentityResolver(identifier_repository, inventory_device_repository)
        self._evidence_dir = evidence_dir

    def run(self, collector: DiscoveryCollector, fixture_name: str | None = None) -> DiscoveryRunEvidence:
        execution_id = self._new_execution_id()
        started_at = datetime.now().astimezone()
        errors: list[str] = []
        results: list[DiscoveryRunResultItem] = []
        devices_created = 0
        devices_updated = 0
        possible_duplicates = 0
        identity_conflicts = 0
        ignored = 0
        observations_normalized = 0

        try:
            raw_observations = collector.collect()
        except DiscoveryFixtureError as exc:
            finished_at = datetime.now().astimezone()
            evidence = DiscoveryRunEvidence(
                execution_id=execution_id,
                collector=str(collector.collector_type.value),
                fixture=fixture_name,
                started_at=started_at,
                finished_at=finished_at,
                errors=[exc.friendly_message if exc.detail is None else f"{exc.friendly_message} ({exc.detail})"],
            )
            self._write_evidence(evidence)
            return evidence

        # First pass: resolve identity per observation and persist devices.
        # Parent links are wired in a second pass so a child observed before
        # its parent (e.g. Thread node before its gateway) still links up.
        pending_links: list[tuple[str, int, ObservationType]] = []

        for raw in raw_observations:
            normalized = normalize_observation(raw)
            errors.extend(normalized.normalization_errors)
            if not normalized.normalization_errors:
                observations_normalized += 1

            resolution = self._resolver.resolve(normalized)
            device_id: int | None = None
            device_name: str | None = None

            if resolution.status == CorrelationStatus.MATCHED_DEVICE:
                device_id = resolution.resolved_device_id
                self._devices.touch_last_seen(device_id, normalized.observed_at)
                self._persist_evidence_for_device(device_id, normalized)
                device = self._devices.get_by_id(device_id)
                device_name = device.name if device else None
                devices_updated += 1
            elif resolution.status in (CorrelationStatus.NEW_DEVICE, CorrelationStatus.POSSIBLE_DUPLICATE):
                device_id = self._create_pending_device(normalized)
                self._persist_evidence_for_device(device_id, normalized)
                device = self._devices.get_by_id(device_id)
                device_name = device.name if device else None
                devices_created += 1
                if resolution.status == CorrelationStatus.POSSIBLE_DUPLICATE:
                    possible_duplicates += 1
            elif resolution.status == CorrelationStatus.IDENTITY_CONFLICT:
                identity_conflicts += 1
            else:  # INSUFFICIENT_EVIDENCE
                ignored += 1

            if device_id is not None and normalized.parent_hostname:
                pending_links.append((normalized.parent_hostname, device_id, normalized.observation_type))

            self._observations.save(
                collector_id=normalized.collector_id,
                collector_type=normalized.collector_type,
                observed_at=normalized.observed_at,
                observation_type=normalized.observation_type,
                source=normalized.source,
                raw_payload_json=json.dumps(normalized.raw_payload, ensure_ascii=False, default=str),
                normalized_payload_json=normalized.model_dump_json(),
                confidence=resolution.confidence,
                correlation_status=resolution.status,
                resolved_device_id=device_id,
            )

            results.append(
                DiscoveryRunResultItem(
                    observation_type=normalized.observation_type,
                    source=normalized.source,
                    correlation_status=resolution.status,
                    confidence=resolution.confidence,
                    device_id=device_id,
                    device_name=device_name,
                    notes=resolution.notes,
                )
            )

        for parent_hostname, child_device_id, observation_type in pending_links:
            self._link_parent(parent_hostname, child_device_id, observation_type)

        finished_at = datetime.now().astimezone()
        evidence = DiscoveryRunEvidence(
            execution_id=execution_id,
            collector=str(raw_observations[0].collector_type.value) if raw_observations else "unknown",
            fixture=fixture_name,
            started_at=started_at,
            finished_at=finished_at,
            observations_received=len(raw_observations),
            observations_normalized=observations_normalized,
            devices_created=devices_created,
            devices_updated=devices_updated,
            possible_duplicates=possible_duplicates,
            identity_conflicts=identity_conflicts,
            ignored=ignored,
            errors=errors,
            results=results,
        )
        evidence_path = self._write_evidence(evidence)
        logger.info(
            "Descubrimiento finalizado execution_id=%s creados=%s actualizados=%s conflictos=%s evidencia=%s",
            execution_id,
            devices_created,
            devices_updated,
            identity_conflicts,
            evidence_path,
        )
        return evidence

    def _persist_evidence_for_device(self, device_id: int, normalized: NormalizedObservation) -> None:
        for identifier in normalized.identifiers:
            self._identifiers.upsert(
                device_id=device_id,
                identifier_type=identifier.identifier_type,
                identifier_value=identifier.value,
                normalized_value=identifier.normalized_value,
                confidence=identifier.confidence,
                source=normalized.source,
                seen_at=normalized.observed_at,
            )
        for address in normalized.addresses:
            self._addresses.upsert(
                device_id=device_id,
                address=address.address,
                address_family=address.address_family,
                scope=address.scope,
                source=normalized.source,
                seen_at=normalized.observed_at,
                prefix_length=address.prefix_length,
            )

        interface_type = _INTERFACE_OBSERVATION_TYPES.get(normalized.observation_type)
        mac_identifier = next(
            (i for i in normalized.identifiers if i.identifier_type == IdentifierType.MAC), None
        )
        if interface_type and mac_identifier:
            self._interfaces.upsert(
                device_id=device_id,
                name=interface_type,
                interface_type=interface_type,
                mac_address=mac_identifier.normalized_value,
                state="up",
                seen_at=normalized.observed_at,
            )

    def _create_pending_device(self, normalized: NormalizedObservation) -> int:
        name = normalized.hostname or self._fallback_name(normalized)
        device_type = normalized.device_type_hint or DeviceType.UNKNOWN
        record = self._devices.create(
            name=name,
            alias=name,
            device_type=device_type,
            management_status=DeviceManagementStatus.UNMANAGED,
            discovery_status=DeviceDiscoveryStatus.PENDING_APPROVAL,
            source=f"discovery:{normalized.collector_id}",
            manufacturer=normalized.manufacturer_hint,
            seen_at=normalized.observed_at,
        )
        return record.id

    def _link_parent(self, parent_hostname: str, child_device_id: int, observation_type: ObservationType) -> None:
        parent_identifier = self._identifiers.find_by_value(IdentifierType.HOSTNAME, parent_hostname)
        if parent_identifier is None or parent_identifier.device_id == child_device_id:
            return
        link_type_name = _LINK_TYPE_BY_OBSERVATION.get(observation_type, "UNKNOWN")
        link_type = LinkType[link_type_name] if link_type_name in LinkType.__members__ else LinkType.UNKNOWN
        self._topology_links.upsert(
            source_device_id=parent_identifier.device_id,
            target_device_id=child_device_id,
            link_type=link_type,
            seen_at=datetime.now().astimezone(),
        )

    @staticmethod
    def _fallback_name(normalized: NormalizedObservation) -> str:
        for identifier in normalized.identifiers:
            if identifier.identifier_type in (IdentifierType.MAC, IdentifierType.AGENT_ID, IdentifierType.SERIAL):
                return f"{normalized.observation_type.value.lower()}-{identifier.normalized_value}"
        return f"{normalized.observation_type.value.lower()}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _new_execution_id() -> str:
        today = datetime.now().strftime("%Y%m%d")
        return f"disc-{today}-{uuid.uuid4().hex[:8]}"

    def _write_evidence(self, evidence: DiscoveryRunEvidence) -> Path | None:
        try:
            started = evidence.started_at
            day_dir = self._evidence_dir / f"{started:%Y}" / f"{started:%m}" / f"{started:%d}"
            day_dir.mkdir(parents=True, exist_ok=True)
            evidence_path = day_dir / f"{evidence.execution_id}.json"
            payload = json.loads(evidence.model_dump_json())
            evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return evidence_path
        except OSError:
            logger.exception("No fue posible escribir la evidencia de descubrimiento %s", evidence.execution_id)
            return None
