from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

import repositories.device_repository  # noqa: F401 - registers `devices` before create_all (gateway_id FK target)
from core.exceptions import InventoryDeviceNotFoundError
from discovery.enums import DeviceDiscoveryStatus, DeviceManagementStatus, DeviceType
from repositories.database import Base, get_engine, get_session_factory, init_db, naive


class InventoryDeviceRecord(Base):
    """A device known to the inventory — manually registered, discovered and
    pending approval, approved/managed, ignored, or gone stale.

    Deliberately separate from `devices` (repositories/device_repository.py):
    `devices` is the narrower "SSH-connectable gateway" registry used by
    Conexión/Comandos/Diagnóstico. `gateway_id` below links an inventory
    device to its `devices` row when the two coincide (e.g. an approved
    OpenWrt router that's also configured for SSH access).
    """

    __tablename__ = "inventory_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    alias: Mapped[str] = mapped_column(String, index=True)
    device_type: Mapped[str] = mapped_column(String, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    platform: Mapped[str | None] = mapped_column(String, nullable=True)
    platform_version: Mapped[str | None] = mapped_column(String, nullable=True)
    management_status: Mapped[str] = mapped_column(String, index=True)
    discovery_status: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String)
    created_manually: Mapped[bool] = mapped_column(default=False)
    parent_device_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_devices.id"), nullable=True
    )
    gateway_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column()
    last_seen_at: Mapped[datetime] = mapped_column()
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ignored_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()
    metadata_json: Mapped[str] = mapped_column(String, default="{}")


class InventoryDeviceRepository:
    """Persists the broader device inventory (manual + discovered devices) to SQLite."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def create(
        self,
        *,
        name: str,
        alias: str,
        device_type: DeviceType,
        management_status: DeviceManagementStatus,
        discovery_status: DeviceDiscoveryStatus,
        source: str,
        created_manually: bool = False,
        manufacturer: str | None = None,
        model: str | None = None,
        platform: str | None = None,
        platform_version: str | None = None,
        parent_device_id: int | None = None,
        gateway_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        seen_at: datetime | None = None,
    ) -> InventoryDeviceRecord:
        now = seen_at or datetime.now().astimezone()
        approved_at = now if discovery_status == DeviceDiscoveryStatus.APPROVED else None
        record = InventoryDeviceRecord(
            name=name,
            alias=alias,
            device_type=device_type.value,
            manufacturer=manufacturer,
            model=model,
            platform=platform,
            platform_version=platform_version,
            management_status=management_status.value,
            discovery_status=discovery_status.value,
            source=source,
            created_manually=created_manually,
            parent_device_id=parent_device_id,
            gateway_id=gateway_id,
            first_seen_at=now,
            last_seen_at=now,
            approved_at=approved_at,
            created_at=now,
            updated_at=now,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        with self._session_factory() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get_by_id(self, device_id: int) -> InventoryDeviceRecord | None:
        with self._session_factory() as session:
            return session.get(InventoryDeviceRecord, device_id)

    def list_all(
        self,
        *,
        discovery_status: DeviceDiscoveryStatus | None = None,
        management_status: DeviceManagementStatus | None = None,
    ) -> list[InventoryDeviceRecord]:
        with self._session_factory() as session:
            stmt = select(InventoryDeviceRecord).order_by(InventoryDeviceRecord.name)
            if discovery_status is not None:
                stmt = stmt.where(InventoryDeviceRecord.discovery_status == discovery_status.value)
            if management_status is not None:
                stmt = stmt.where(InventoryDeviceRecord.management_status == management_status.value)
            return list(session.scalars(stmt).all())

    def touch_last_seen(self, device_id: int, seen_at: datetime) -> None:
        with self._session_factory() as session:
            record = session.get(InventoryDeviceRecord, device_id)
            if record is None:
                raise InventoryDeviceNotFoundError(f"device_id={device_id}")
            if naive(seen_at) > naive(record.last_seen_at):
                record.last_seen_at = seen_at
            record.updated_at = datetime.now().astimezone()
            session.commit()

    def update_status(
        self,
        device_id: int,
        *,
        discovery_status: DeviceDiscoveryStatus | None = None,
        management_status: DeviceManagementStatus | None = None,
        approved_at: datetime | None = None,
        ignored_at: datetime | None = None,
    ) -> InventoryDeviceRecord:
        with self._session_factory() as session:
            record = session.get(InventoryDeviceRecord, device_id)
            if record is None:
                raise InventoryDeviceNotFoundError(f"device_id={device_id}")
            if discovery_status is not None:
                record.discovery_status = discovery_status.value
            if management_status is not None:
                record.management_status = management_status.value
            if approved_at is not None:
                record.approved_at = approved_at
            if ignored_at is not None:
                record.ignored_at = ignored_at
            record.updated_at = datetime.now().astimezone()
            session.commit()
            session.refresh(record)
            return record

    def update_fields(
        self,
        device_id: int,
        *,
        name: str | None = None,
        alias: str | None = None,
        device_type: DeviceType | None = None,
        gateway_id: int | None = None,
        parent_device_id: int | None = None,
    ) -> InventoryDeviceRecord:
        with self._session_factory() as session:
            record = session.get(InventoryDeviceRecord, device_id)
            if record is None:
                raise InventoryDeviceNotFoundError(f"device_id={device_id}")
            if name is not None:
                record.name = name
            if alias is not None:
                record.alias = alias
            if device_type is not None:
                record.device_type = device_type.value
            if gateway_id is not None:
                record.gateway_id = gateway_id
            if parent_device_id is not None:
                record.parent_device_id = parent_device_id
            record.updated_at = datetime.now().astimezone()
            session.commit()
            session.refresh(record)
            return record

    def delete(self, device_id: int) -> None:
        with self._session_factory() as session:
            session.execute(delete(InventoryDeviceRecord).where(InventoryDeviceRecord.id == device_id))
            session.commit()

    def stats(self) -> dict:
        with self._session_factory() as session:
            records = list(session.scalars(select(InventoryDeviceRecord)).all())
        by_status: dict[str, int] = {}
        for record in records:
            by_status[record.discovery_status] = by_status.get(record.discovery_status, 0) + 1
        return {"total": len(records), "by_status": by_status}
