from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

import discovery.repositories.inventory_device_repository  # noqa: F401 - registers inventory_devices before create_all
from discovery.enums import AddressFamily, AddressScope
from repositories.database import Base, get_engine, get_session_factory, init_db, naive


class DeviceAddressRecord(Base):
    __tablename__ = "device_addresses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("inventory_devices.id"), index=True)
    address: Mapped[str] = mapped_column(String, index=True)
    address_family: Mapped[str] = mapped_column(String)
    scope: Mapped[str] = mapped_column(String)
    prefix_length: Mapped[int | None] = mapped_column(nullable=True)
    is_current: Mapped[bool] = mapped_column(default=True)
    first_seen_at: Mapped[datetime] = mapped_column()
    last_seen_at: Mapped[datetime] = mapped_column()
    source: Mapped[str] = mapped_column(String)


class DeviceAddressRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def list_for_device(self, device_id: int) -> list[DeviceAddressRecord]:
        with self._session_factory() as session:
            stmt = select(DeviceAddressRecord).where(DeviceAddressRecord.device_id == device_id)
            return list(session.scalars(stmt).all())

    def upsert(
        self,
        *,
        device_id: int,
        address: str,
        address_family: AddressFamily,
        scope: AddressScope,
        source: str,
        seen_at: datetime,
        prefix_length: int | None = None,
    ) -> DeviceAddressRecord:
        with self._session_factory() as session:
            stmt = select(DeviceAddressRecord).where(
                DeviceAddressRecord.device_id == device_id,
                DeviceAddressRecord.address == address,
            )
            existing = session.scalars(stmt).first()
            if existing is not None:
                if naive(seen_at) > naive(existing.last_seen_at):
                    existing.last_seen_at = seen_at
                existing.is_current = True
                session.commit()
                session.refresh(existing)
                return existing

            # IPv4 is normally a single DHCP-assigned address per device, so
            # a genuinely new one supersedes the old one (device roamed to a
            # new lease). IPv6 devices legitimately hold several simultaneous
            # current addresses (link-local + ULA/global) — never collapse
            # those, or the "multiple IPv6 addresses" case would be lost.
            if address_family == AddressFamily.IPV4:
                other_stmt = select(DeviceAddressRecord).where(
                    DeviceAddressRecord.device_id == device_id,
                    DeviceAddressRecord.address_family == AddressFamily.IPV4.value,
                    DeviceAddressRecord.is_current.is_(True),
                )
                for other in session.scalars(other_stmt).all():
                    other.is_current = False

            record = DeviceAddressRecord(
                device_id=device_id,
                address=address,
                address_family=address_family.value,
                scope=scope.value,
                prefix_length=prefix_length,
                is_current=True,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                source=source,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def reassign_device(self, from_device_id: int, to_device_id: int) -> int:
        with self._session_factory() as session:
            stmt = select(DeviceAddressRecord).where(DeviceAddressRecord.device_id == from_device_id)
            records = list(session.scalars(stmt).all())
            for record in records:
                record.device_id = to_device_id
            session.commit()
            return len(records)
