from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.engine import Engine

from core.exceptions import InvalidMergeError
from discovery.enums import DeviceDiscoveryStatus
from discovery.models import MergePreview
from discovery.repositories.address_repository import DeviceAddressRecord
from discovery.repositories.identifier_repository import DeviceIdentifierRecord
from discovery.repositories.interface_repository import DeviceInterfaceRecord
from discovery.repositories.inventory_device_repository import InventoryDeviceRecord
from discovery.repositories.observation_repository import DiscoveryObservationRecord
from discovery.repositories.topology_link_repository import TopologyLinkRecord
from repositories.database import get_engine, get_session_factory, init_db

logger = logging.getLogger(__name__)


class MergePlanner:
    """Merges one inventory device into another inside a single DB
    transaction (spec section 11): identifiers, addresses, interfaces,
    observations, and topology links all move to the target; the source is
    kept (marked REMOVED) rather than deleted, so history is never lost.
    Any failure mid-merge rolls the whole transaction back — nothing is
    left half-moved.
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def preview(self, source_device_id: int, target_device_id: int) -> MergePreview:
        with self._session_factory() as session:
            source = session.get(InventoryDeviceRecord, source_device_id)
            target = session.get(InventoryDeviceRecord, target_device_id)
            self._validate(source, target, source_device_id, target_device_id)

            identifiers = session.query(DeviceIdentifierRecord).filter_by(device_id=source_device_id).count()
            addresses = session.query(DeviceAddressRecord).filter_by(device_id=source_device_id).count()
            interfaces = session.query(DeviceInterfaceRecord).filter_by(device_id=source_device_id).count()
            observations = (
                session.query(DiscoveryObservationRecord).filter_by(resolved_device_id=source_device_id).count()
            )
            return MergePreview(
                source_device_id=source_device_id,
                source_name=source.name,
                target_device_id=target_device_id,
                target_name=target.name,
                identifiers_to_move=identifiers,
                addresses_to_move=addresses,
                interfaces_to_move=interfaces,
                observations_to_move=observations,
            )

    def merge(self, source_device_id: int, target_device_id: int, *, confirmed: bool) -> None:
        if not confirmed:
            raise InvalidMergeError("La fusión requiere confirmación explícita.")

        with self._session_factory() as session:
            try:
                source = session.get(InventoryDeviceRecord, source_device_id)
                target = session.get(InventoryDeviceRecord, target_device_id)
                self._validate(source, target, source_device_id, target_device_id)

                session.execute(
                    update(DeviceIdentifierRecord)
                    .where(DeviceIdentifierRecord.device_id == source_device_id)
                    .values(device_id=target_device_id)
                )
                session.execute(
                    update(DeviceAddressRecord)
                    .where(DeviceAddressRecord.device_id == source_device_id)
                    .values(device_id=target_device_id)
                )
                session.execute(
                    update(DeviceInterfaceRecord)
                    .where(DeviceInterfaceRecord.device_id == source_device_id)
                    .values(device_id=target_device_id)
                )
                session.execute(
                    update(DiscoveryObservationRecord)
                    .where(DiscoveryObservationRecord.resolved_device_id == source_device_id)
                    .values(resolved_device_id=target_device_id)
                )
                session.execute(
                    update(TopologyLinkRecord)
                    .where(TopologyLinkRecord.source_device_id == source_device_id)
                    .values(source_device_id=target_device_id)
                )
                session.execute(
                    update(TopologyLinkRecord)
                    .where(TopologyLinkRecord.target_device_id == source_device_id)
                    .values(target_device_id=target_device_id)
                )

                now = datetime.now().astimezone()
                source.discovery_status = DeviceDiscoveryStatus.REMOVED.value
                source.updated_at = now
                target.last_seen_at = max(target.last_seen_at, source.last_seen_at)
                target.updated_at = now

                session.commit()
            except Exception:
                session.rollback()
                logger.exception(
                    "Fusión revertida: source=%s target=%s", source_device_id, target_device_id
                )
                raise

    @staticmethod
    def _validate(
        source: InventoryDeviceRecord | None,
        target: InventoryDeviceRecord | None,
        source_device_id: int,
        target_device_id: int,
    ) -> None:
        if source_device_id == target_device_id:
            raise InvalidMergeError("El dispositivo origen y destino no pueden ser el mismo.")
        if source is None or target is None:
            raise InvalidMergeError("El dispositivo origen o destino no existe.")
        if source.discovery_status == DeviceDiscoveryStatus.REMOVED.value:
            raise InvalidMergeError("El dispositivo origen ya fue fusionado anteriormente.")
