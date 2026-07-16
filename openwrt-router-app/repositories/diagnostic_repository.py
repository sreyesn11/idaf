from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import Float, Integer, String, Text, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

from diagnostics.enums import DiagnosticState
from diagnostics.models import RouterDiagnosticResult
from repositories.database import Base, get_engine, get_session_factory, init_db


class DiagnosticRecord(Base):
    __tablename__ = "diagnostics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    diagnostic_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    diagnostic_type: Mapped[str] = mapped_column(String, index=True)
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    target_device_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    target_host: Mapped[str] = mapped_column("target", String)
    state: Mapped[str] = mapped_column(String, index=True)
    summary: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column()
    finished_at: Mapped[datetime] = mapped_column()
    duration_seconds: Mapped[float] = mapped_column(Float)
    checks_json: Mapped[str] = mapped_column(Text)
    evidence_execution_ids_json: Mapped[str] = mapped_column(Text)
    warnings_json: Mapped[str] = mapped_column(Text)
    evidence_path: Mapped[str | None] = mapped_column(String, nullable=True)


class DiagnosticRepository:
    """Persists RouterDiagnosticResult objects to SQLite, in a table separate from `executions`."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def save(
        self,
        result: RouterDiagnosticResult,
        evidence_path: Path | None = None,
        device_id: int | None = None,
    ) -> None:
        with self._session_factory() as session:
            record = DiagnosticRecord(
                diagnostic_id=result.diagnostic_id,
                diagnostic_type=result.diagnostic_type,
                device_id=device_id,
                target_device_id=result.target_device_id,
                target_host=result.target_host,
                state=result.state.value,
                summary=result.summary,
                started_at=result.started_at,
                finished_at=result.finished_at,
                duration_seconds=result.duration_seconds,
                checks_json=json.dumps([c.model_dump(mode="json") for c in result.checks], ensure_ascii=False),
                evidence_execution_ids_json=json.dumps(result.evidence_execution_ids, ensure_ascii=False),
                warnings_json=json.dumps(result.warnings, ensure_ascii=False),
                evidence_path=str(evidence_path) if evidence_path else None,
            )
            session.add(record)
            session.commit()

    def list_all(
        self,
        state: str | None = None,
        search: str | None = None,
        device_id: int | None = None,
    ) -> list[DiagnosticRecord]:
        with self._session_factory() as session:
            stmt = select(DiagnosticRecord).order_by(DiagnosticRecord.started_at.desc())
            if state:
                stmt = stmt.where(DiagnosticRecord.state == state)
            if device_id is not None:
                stmt = stmt.where(DiagnosticRecord.device_id == device_id)
            if search:
                like = f"%{search}%"
                stmt = stmt.where((DiagnosticRecord.target_host.like(like)) | (DiagnosticRecord.summary.like(like)))
            return list(session.scalars(stmt).all())

    def get_by_diagnostic_id(self, diagnostic_id: str) -> DiagnosticRecord | None:
        with self._session_factory() as session:
            stmt = select(DiagnosticRecord).where(DiagnosticRecord.diagnostic_id == diagnostic_id)
            return session.scalars(stmt).first()

    def get_latest_for_target(self, target_device_id: str) -> DiagnosticRecord | None:
        with self._session_factory() as session:
            stmt = (
                select(DiagnosticRecord)
                .where(DiagnosticRecord.target_device_id == target_device_id)
                .order_by(DiagnosticRecord.started_at.desc())
                .limit(1)
            )
            return session.scalars(stmt).first()

    def delete_by_diagnostic_id(self, diagnostic_id: str) -> None:
        with self._session_factory() as session:
            session.execute(delete(DiagnosticRecord).where(DiagnosticRecord.diagnostic_id == diagnostic_id))
            session.commit()

    def clear_all(self) -> None:
        with self._session_factory() as session:
            session.execute(delete(DiagnosticRecord))
            session.commit()

    def stats(self) -> dict:
        with self._session_factory() as session:
            total = session.scalar(select(func.count()).select_from(DiagnosticRecord)) or 0
            healthy = (
                session.scalar(
                    select(func.count())
                    .select_from(DiagnosticRecord)
                    .where(DiagnosticRecord.state == DiagnosticState.HEALTHY.value)
                )
                or 0
            )
            warning = (
                session.scalar(
                    select(func.count())
                    .select_from(DiagnosticRecord)
                    .where(DiagnosticRecord.state == DiagnosticState.WARNING.value)
                )
                or 0
            )
            degraded_or_critical = (
                session.scalar(
                    select(func.count())
                    .select_from(DiagnosticRecord)
                    .where(
                        DiagnosticRecord.state.in_(
                            [
                                DiagnosticState.DEGRADED.value,
                                DiagnosticState.CRITICAL.value,
                                DiagnosticState.UNREACHABLE.value,
                            ]
                        )
                    )
                )
                or 0
            )
            latest = session.scalars(
                select(DiagnosticRecord).order_by(DiagnosticRecord.started_at.desc()).limit(1)
            ).first()
            return {
                "total": total,
                "healthy": healthy,
                "warning": warning,
                "degraded_or_critical": degraded_or_critical,
                "latest": latest,
            }
