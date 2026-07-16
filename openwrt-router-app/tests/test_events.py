from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from diagnostics.enums import DiagnosticState
from events.event_repository import EventRepository
from events.models import StateChangeEvent
from repositories.database import get_engine


@pytest.fixture()
def repository(tmp_path: Path) -> EventRepository:
    engine = get_engine(tmp_path / "history.db")
    return EventRepository(engine=engine)


def _make_event(
    target_device_id: str = "lab-gateway-1",
    from_state: DiagnosticState = DiagnosticState.HEALTHY,
    to_state: DiagnosticState = DiagnosticState.WARNING,
    timestamp: datetime = datetime(2026, 7, 16, 10, 0, 0),
) -> StateChangeEvent:
    return StateChangeEvent(
        target_device_id=target_device_id,
        from_state=from_state,
        to_state=to_state,
        timestamp=timestamp,
    )


def test_save_and_list_all(repository: EventRepository) -> None:
    repository.save(_make_event())
    records = repository.list_all()
    assert len(records) == 1
    assert records[0].target_device_id == "lab-gateway-1"
    assert records[0].from_state == DiagnosticState.HEALTHY.value
    assert records[0].to_state == DiagnosticState.WARNING.value
    assert records[0].event_type == "state_change"
    assert records[0].source == "router_general_health"


def test_search_filters_by_target_device_id(repository: EventRepository) -> None:
    repository.save(_make_event(target_device_id="lab-gateway-1"))
    repository.save(_make_event(target_device_id="lab-gateway-2"))
    records = repository.list_all(search="lab-gateway-2")
    assert [r.target_device_id for r in records] == ["lab-gateway-2"]


def test_clear_all(repository: EventRepository) -> None:
    repository.save(_make_event())
    repository.clear_all()
    assert repository.list_all() == []


def test_stats_returns_latest(repository: EventRepository) -> None:
    repository.save(_make_event(timestamp=datetime(2026, 7, 16, 10, 0, 0)))
    repository.save(_make_event(timestamp=datetime(2026, 7, 16, 11, 0, 0)))

    latest = repository.stats()["latest"]

    assert latest is not None
    assert latest.timestamp == datetime(2026, 7, 16, 11, 0, 0)


def test_stats_latest_is_none_when_empty(repository: EventRepository) -> None:
    assert repository.stats()["latest"] is None
