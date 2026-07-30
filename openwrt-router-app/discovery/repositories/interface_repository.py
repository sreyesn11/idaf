from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

import discovery.repositories.inventory_device_repository  # noqa: F401 - registers inventory_devices before create_all
from repositories.database import Base, get_engine, get_session_factory, init_db, naive


class DeviceInterfaceRecord(Base):
    __tablename__ = "device_interfaces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("inventory_devices.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    interface_type: Mapped[str] = mapped_column(String)
    mac_address: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    state: Mapped[str] = mapped_column(String, default="unknown")
    first_seen_at: Mapped[datetime] = mapped_column()
    last_seen_at: Mapped[datetime] = mapped_column()
    metadata_json: Mapped[str] = mapped_column(String, default="{}")


class DeviceInterfaceRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def list_for_device(self, device_id: int) -> list[DeviceInterfaceRecord]:
        with self._session_factory() as session:
            stmt = select(DeviceInterfaceRecord).where(DeviceInterfaceRecord.device_id == device_id)
            return list(session.scalars(stmt).all())

    def upsert(
        self,
        *,
        device_id: int,
        name: str,
        interface_type: str,
        mac_address: str | None,
        state: str,
        seen_at: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> DeviceInterfaceRecord:
        with self._session_factory() as session:
            stmt = select(DeviceInterfaceRecord).where(
                DeviceInterfaceRecord.device_id == device_id,
                DeviceInterfaceRecord.name == name,
            )
            existing = session.scalars(stmt).first()
            if existing is not None:
                existing.state = state
                if naive(seen_at) > naive(existing.last_seen_at):
                    existing.last_seen_at = seen_at
                if mac_address:
                    existing.mac_address = mac_address
                session.commit()
                session.refresh(existing)
                return existing

            record = DeviceInterfaceRecord(
                device_id=device_id,
                name=name,
                interface_type=interface_type,
                mac_address=mac_address,
                state=state,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def reassign_device(self, from_device_id: int, to_device_id: int) -> int:
        with self._session_factory() as session:
            stmt = select(DeviceInterfaceRecord).where(DeviceInterfaceRecord.device_id == from_device_id)
            records = list(session.scalars(stmt).all())
            for record in records:
                record.device_id = to_device_id
            session.commit()
            return len(records)
