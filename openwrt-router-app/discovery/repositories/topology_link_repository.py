from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

import discovery.repositories.inventory_device_repository  # noqa: F401 - registers inventory_devices before create_all
from discovery.enums import LinkType
from repositories.database import Base, get_engine, get_session_factory, init_db, naive


class TopologyLinkRecord(Base):
    """A persisted edge between two inventory devices.

    Distinct from `topology.models.TopologyLink` (the in-memory Pydantic
    model `topology/renderer.py` draws) — that one is a rendering DTO built
    fresh on every page load; this is the durable relationship it can be
    built *from* once a link is discovered/approved.
    """

    __tablename__ = "topology_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_device_id: Mapped[int] = mapped_column(ForeignKey("inventory_devices.id"), index=True)
    target_device_id: Mapped[int] = mapped_column(ForeignKey("inventory_devices.id"), index=True)
    link_type: Mapped[str] = mapped_column(String)
    protocol: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, default="UNKNOWN")
    first_seen_at: Mapped[datetime] = mapped_column()
    last_seen_at: Mapped[datetime] = mapped_column()
    metadata_json: Mapped[str] = mapped_column(String, default="{}")


class TopologyLinkRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()
        init_db(self._engine)
        self._session_factory = get_session_factory(self._engine)

    def upsert(
        self,
        *,
        source_device_id: int,
        target_device_id: int,
        link_type: LinkType,
        seen_at: datetime,
        protocol: str | None = None,
        state: str = "UNKNOWN",
        metadata: dict[str, Any] | None = None,
    ) -> TopologyLinkRecord:
        """Create the link, or refresh it if this exact source/target/type
        edge already exists — avoids duplicate parallel edges on re-runs."""
        with self._session_factory() as session:
            stmt = select(TopologyLinkRecord).where(
                TopologyLinkRecord.source_device_id == source_device_id,
                TopologyLinkRecord.target_device_id == target_device_id,
                TopologyLinkRecord.link_type == link_type.value,
            )
            existing = session.scalars(stmt).first()
            if existing is not None:
                existing.state = state
                if naive(seen_at) > naive(existing.last_seen_at):
                    existing.last_seen_at = seen_at
                session.commit()
                session.refresh(existing)
                return existing

            record = TopologyLinkRecord(
                source_device_id=source_device_id,
                target_device_id=target_device_id,
                link_type=link_type.value,
                protocol=protocol,
                state=state,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def list_all(self) -> list[TopologyLinkRecord]:
        with self._session_factory() as session:
            return list(session.scalars(select(TopologyLinkRecord)).all())

    def list_for_device(self, device_id: int) -> list[TopologyLinkRecord]:
        with self._session_factory() as session:
            stmt = select(TopologyLinkRecord).where(
                (TopologyLinkRecord.source_device_id == device_id)
                | (TopologyLinkRecord.target_device_id == device_id)
            )
            return list(session.scalars(stmt).all())
