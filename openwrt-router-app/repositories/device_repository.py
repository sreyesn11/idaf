from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

# Imported (even if unused) so their tables are registered on Base.metadata
# before create_all runs, in case DeviceRepository is constructed first.
import repositories.diagnostic_repository  # noqa: F401
import repositories.execution_repository  # noqa: F401
from core.exceptions import DeviceAliasAlreadyExistsError, DeviceNotFoundError
from models.device import DeviceConfig
from repositories.database import Base, get_engine, get_session_factory, init_db


class DeviceRecord(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String, unique=True, index=True)
    host: Mapped[str] = mapped_column(String)
    port: Mapped[int] = mapped_column(Integer)
    username: Mapped[str] = mapped_column(String)
    timeout: Mapped[int] = mapped_column(Integer)
    host_key_policy: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column()
    # Intentionally no password column: the password is never persisted.


class DeviceRepository:
    """Persists the registry of saved gateways (no credentials) to SQLite."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def create(self, device: DeviceConfig) -> DeviceRecord:
        record = DeviceRecord(
            alias=device.alias,
            host=device.host,
            port=device.port,
            username=device.username,
            timeout=device.timeout,
            host_key_policy=device.host_key_policy.value,
            created_at=device.created_at or datetime.now().astimezone(),
        )
        with self._session_factory() as session:
            session.add(record)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DeviceAliasAlreadyExistsError(f"alias duplicado: {device.alias}") from exc
            session.refresh(record)
            return record

    def list_all(self) -> list[DeviceRecord]:
        with self._session_factory() as session:
            stmt = select(DeviceRecord).order_by(DeviceRecord.alias)
            return list(session.scalars(stmt).all())

    def get_by_id(self, device_id: int) -> DeviceRecord | None:
        with self._session_factory() as session:
            return session.get(DeviceRecord, device_id)

    def update(self, device_id: int, device: DeviceConfig) -> None:
        with self._session_factory() as session:
            record = session.get(DeviceRecord, device_id)
            if record is None:
                raise DeviceNotFoundError(f"device_id={device_id}")
            record.alias = device.alias
            record.host = device.host
            record.port = device.port
            record.username = device.username
            record.timeout = device.timeout
            record.host_key_policy = device.host_key_policy.value
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise DeviceAliasAlreadyExistsError(f"alias duplicado: {device.alias}") from exc

    def delete(self, device_id: int) -> None:
        with self._session_factory() as session:
            session.execute(delete(DeviceRecord).where(DeviceRecord.id == device_id))
            session.commit()
