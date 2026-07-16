from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import Float, Integer, String, Text, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

from models.execution import ExecutionResult, ExecutionStatus
from repositories.database import Base, get_engine, get_session_factory, init_db


class ExecutionRecord(Base):
    __tablename__ = "executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    command_id: Mapped[str] = mapped_column(String, index=True)
    command_name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, index=True)
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    host: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(String)
    command: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, index=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column()
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    stdout: Mapped[str] = mapped_column(Text)
    stderr: Mapped[str] = mapped_column(Text)
    parsed_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_message: Mapped[str] = mapped_column(Text)
    technical_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String, nullable=True)


class ExecutionRepository:
    """Persists ExecutionResult objects to SQLite. Never persists the SSH password."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def save(self, result: ExecutionResult, evidence_path: Path | None = None, device_id: int | None = None) -> None:
        with self._session_factory() as session:
            record = ExecutionRecord(
                execution_id=result.execution_id,
                command_id=result.command_id,
                command_name=result.command_name,
                category=result.category,
                device_id=device_id,
                host=result.host,
                port=result.port,
                username=result.username,
                command=result.command,
                status=result.status.value,
                exit_code=result.exit_code,
                started_at=result.started_at,
                finished_at=result.finished_at,
                duration_seconds=result.duration_seconds,
                stdout=result.stdout,
                stderr=result.stderr,
                parsed_data_json=(
                    json.dumps(result.parsed_data, ensure_ascii=False) if result.parsed_data is not None else None
                ),
                user_message=result.user_message,
                technical_message=result.technical_message,
                evidence_path=str(evidence_path) if evidence_path else None,
            )
            session.add(record)
            session.commit()

    def list_all(
        self,
        status: str | None = None,
        category: str | None = None,
        search: str | None = None,
        device_id: int | None = None,
    ) -> list[ExecutionRecord]:
        with self._session_factory() as session:
            stmt = select(ExecutionRecord).order_by(ExecutionRecord.started_at.desc())
            if status:
                stmt = stmt.where(ExecutionRecord.status == status)
            if category:
                stmt = stmt.where(ExecutionRecord.category == category)
            if device_id is not None:
                stmt = stmt.where(ExecutionRecord.device_id == device_id)
            if search:
                like = f"%{search}%"
                stmt = stmt.where(
                    (ExecutionRecord.command.like(like)) | (ExecutionRecord.command_name.like(like))
                )
            return list(session.scalars(stmt).all())

    def get_by_execution_id(self, execution_id: str) -> ExecutionRecord | None:
        with self._session_factory() as session:
            stmt = select(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id)
            return session.scalars(stmt).first()

    def delete_by_execution_id(self, execution_id: str) -> None:
        with self._session_factory() as session:
            session.execute(delete(ExecutionRecord).where(ExecutionRecord.execution_id == execution_id))
            session.commit()

    def clear_all(self) -> None:
        with self._session_factory() as session:
            session.execute(delete(ExecutionRecord))
            session.commit()

    def stats(self) -> dict:
        with self._session_factory() as session:
            total = session.scalar(select(func.count()).select_from(ExecutionRecord)) or 0
            successful = (
                session.scalar(
                    select(func.count())
                    .select_from(ExecutionRecord)
                    .where(
                        ExecutionRecord.status.in_(
                            [ExecutionStatus.COMPLETED.value, ExecutionStatus.COMPLETED_WITH_WARNINGS.value]
                        )
                    )
                )
                or 0
            )
            failed = total - successful
            return {"total": total, "successful": successful, "failed": failed}
