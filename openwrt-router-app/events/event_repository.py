from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

from events.models import StateChangeEvent
from repositories.database import Base, get_engine, get_session_factory, init_db


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    target_device_id: Mapped[str] = mapped_column(String, index=True)
    from_state: Mapped[str] = mapped_column(String)
    to_state: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column()
    source: Mapped[str] = mapped_column(String)


class EventRepository:
    """Persists StateChangeEvent objects to SQLite, in a table separate from `diagnostics`."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def save(self, event: StateChangeEvent) -> None:
        with self._session_factory() as session:
            record = EventRecord(
                event_type=event.event_type,
                target_device_id=event.target_device_id,
                from_state=event.from_state.value,
                to_state=event.to_state.value,
                timestamp=event.timestamp,
                source=event.source,
            )
            session.add(record)
            session.commit()

    def list_all(self, search: str | None = None) -> list[EventRecord]:
        with self._session_factory() as session:
            stmt = select(EventRecord).order_by(EventRecord.timestamp.desc())
            if search:
                like = f"%{search}%"
                stmt = stmt.where(EventRecord.target_device_id.like(like))
            return list(session.scalars(stmt).all())

    def clear_all(self) -> None:
        with self._session_factory() as session:
            session.execute(delete(EventRecord))
            session.commit()

    def stats(self) -> dict:
        with self._session_factory() as session:
            latest = session.scalars(
                select(EventRecord).order_by(EventRecord.timestamp.desc()).limit(1)
            ).first()
            return {"latest": latest}
