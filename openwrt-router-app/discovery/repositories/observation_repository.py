from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, String, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

import discovery.repositories.inventory_device_repository  # noqa: F401 - registers inventory_devices before create_all
from discovery.enums import CollectorType, CorrelationStatus, ObservationType
from repositories.database import Base, get_engine, get_session_factory, init_db


class DiscoveryObservationRecord(Base):
    __tablename__ = "discovery_observations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    collector_id: Mapped[str] = mapped_column(String, index=True)
    collector_type: Mapped[str] = mapped_column(String)
    observed_at: Mapped[datetime] = mapped_column()
    observation_type: Mapped[str] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String)
    raw_payload_json: Mapped[str] = mapped_column(String)
    normalized_payload_json: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    correlation_status: Mapped[str] = mapped_column(String, index=True)
    resolved_device_id: Mapped[int | None] = mapped_column(
        ForeignKey("inventory_devices.id"), nullable=True, index=True
    )
    evidence_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column()


class DiscoveryObservationRepository:
    """Persists every discovery observation for traceability (spec section 4.4),
    independent of whether it ended up creating, matching, or merely flagging
    a device."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def save(
        self,
        *,
        collector_id: str,
        collector_type: CollectorType,
        observed_at: datetime,
        observation_type: ObservationType,
        source: str,
        raw_payload_json: str,
        normalized_payload_json: str,
        confidence: float,
        correlation_status: CorrelationStatus,
        resolved_device_id: int | None,
        evidence_path: str | None = None,
    ) -> DiscoveryObservationRecord:
        record = DiscoveryObservationRecord(
            collector_id=collector_id,
            collector_type=collector_type.value,
            observed_at=observed_at,
            observation_type=observation_type.value,
            source=source,
            raw_payload_json=raw_payload_json,
            normalized_payload_json=normalized_payload_json,
            confidence=confidence,
            correlation_status=correlation_status.value,
            resolved_device_id=resolved_device_id,
            evidence_path=evidence_path,
            created_at=datetime.now().astimezone(),
        )
        with self._session_factory() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def list_for_device(self, device_id: int) -> list[DiscoveryObservationRecord]:
        with self._session_factory() as session:
            stmt = (
                select(DiscoveryObservationRecord)
                .where(DiscoveryObservationRecord.resolved_device_id == device_id)
                .order_by(DiscoveryObservationRecord.observed_at.desc())
            )
            return list(session.scalars(stmt).all())

    def list_by_correlation_status(self, status: CorrelationStatus) -> list[DiscoveryObservationRecord]:
        with self._session_factory() as session:
            stmt = (
                select(DiscoveryObservationRecord)
                .where(DiscoveryObservationRecord.correlation_status == status.value)
                .order_by(DiscoveryObservationRecord.observed_at.desc())
            )
            return list(session.scalars(stmt).all())

    def reassign_device(self, from_device_id: int, to_device_id: int) -> int:
        with self._session_factory() as session:
            stmt = select(DiscoveryObservationRecord).where(
                DiscoveryObservationRecord.resolved_device_id == from_device_id
            )
            records = list(session.scalars(stmt).all())
            for record in records:
                record.resolved_device_id = to_device_id
            session.commit()
            return len(records)

    def stats(self) -> dict:
        with self._session_factory() as session:
            records = list(session.scalars(select(DiscoveryObservationRecord)).all())
        return {"total": len(records)}
