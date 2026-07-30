from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

import discovery.repositories.inventory_device_repository  # noqa: F401 - registers inventory_devices before create_all
from discovery.enums import IdentifierType
from repositories.database import Base, get_engine, get_session_factory, init_db, naive


class DeviceIdentifierRecord(Base):
    __tablename__ = "device_identifiers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("inventory_devices.id"), index=True)
    identifier_type: Mapped[str] = mapped_column(String, index=True)
    identifier_value: Mapped[str] = mapped_column(String)
    normalized_value: Mapped[str] = mapped_column(String, index=True)
    is_primary: Mapped[bool] = mapped_column(default=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    first_seen_at: Mapped[datetime] = mapped_column()
    last_seen_at: Mapped[datetime] = mapped_column()
    source: Mapped[str] = mapped_column(String)


class DeviceIdentifierRepository:
    """Persists device identifiers and answers 'which device already has this
    identifier?' — the core lookup `DeviceIdentityResolver` runs against.

    A given (identifier_type, normalized_value) pair is expected to belong to
    at most one device: `find_by_value` is what the resolver uses to notice
    when an incoming observation's identifier already points elsewhere.
    """

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def find_by_value(
        self, identifier_type: IdentifierType, normalized_value: str
    ) -> DeviceIdentifierRecord | None:
        with self._session_factory() as session:
            stmt = select(DeviceIdentifierRecord).where(
                DeviceIdentifierRecord.identifier_type == identifier_type.value,
                DeviceIdentifierRecord.normalized_value == normalized_value,
            )
            return session.scalars(stmt).first()

    def list_for_device(self, device_id: int) -> list[DeviceIdentifierRecord]:
        with self._session_factory() as session:
            stmt = select(DeviceIdentifierRecord).where(DeviceIdentifierRecord.device_id == device_id)
            return list(session.scalars(stmt).all())

    def upsert(
        self,
        *,
        device_id: int,
        identifier_type: IdentifierType,
        identifier_value: str,
        normalized_value: str,
        confidence: float,
        source: str,
        seen_at: datetime,
        is_primary: bool = False,
    ) -> DeviceIdentifierRecord:
        """Attach an identifier to a device, or refresh `last_seen_at` if it
        already exists for that exact device (e.g. re-observed each run)."""
        with self._session_factory() as session:
            stmt = select(DeviceIdentifierRecord).where(
                DeviceIdentifierRecord.device_id == device_id,
                DeviceIdentifierRecord.identifier_type == identifier_type.value,
                DeviceIdentifierRecord.normalized_value == normalized_value,
            )
            existing = session.scalars(stmt).first()
            if existing is not None:
                if naive(seen_at) > naive(existing.last_seen_at):
                    existing.last_seen_at = seen_at
                existing.confidence = max(existing.confidence, confidence)
                session.commit()
                session.refresh(existing)
                return existing

            record = DeviceIdentifierRecord(
                device_id=device_id,
                identifier_type=identifier_type.value,
                identifier_value=identifier_value,
                normalized_value=normalized_value,
                is_primary=is_primary,
                confidence=confidence,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                source=source,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def reassign_device(self, from_device_id: int, to_device_id: int) -> int:
        """Move every identifier from one device to another (used by merges).
        Returns how many rows were moved."""
        with self._session_factory() as session:
            stmt = select(DeviceIdentifierRecord).where(DeviceIdentifierRecord.device_id == from_device_id)
            records = list(session.scalars(stmt).all())
            for record in records:
                record.device_id = to_device_id
            session.commit()
            return len(records)
