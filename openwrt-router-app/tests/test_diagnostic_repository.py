from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from diagnostics.enums import DiagnosticState
from diagnostics.models import DiagnosticCheckResult, RouterDiagnosticResult
from repositories.database import get_engine
from repositories.diagnostic_repository import DiagnosticRepository


@pytest.fixture()
def repository(tmp_path: Path) -> DiagnosticRepository:
    engine = get_engine(tmp_path / "history.db")
    return DiagnosticRepository(engine=engine)


def _make_result(
    diagnostic_id: str,
    state: DiagnosticState,
    target_host: str = "192.168.1.1",
    target_device_id: str = "lab-gateway-1",
    started_at: datetime = datetime(2026, 7, 9, 10, 0, 0),
) -> RouterDiagnosticResult:
    return RouterDiagnosticResult(
        diagnostic_id=diagnostic_id,
        target_device_id=target_device_id,
        target_host=target_host,
        state=state,
        summary=f"resumen {state.value}",
        started_at=started_at,
        finished_at=started_at,
        duration_seconds=4.0,
        checks=[DiagnosticCheckResult(check_id="ssh", check_name="Acceso SSH", state=state, summary="")],
        evidence_execution_ids=["exec-1"],
        warnings=[],
    )


def test_save_and_list_all(repository: DiagnosticRepository) -> None:
    repository.save(_make_result("diag-1", DiagnosticState.HEALTHY))
    records = repository.list_all()
    assert len(records) == 1
    assert records[0].diagnostic_id == "diag-1"
    assert records[0].target_device_id == "lab-gateway-1"
    assert records[0].target_host == "192.168.1.1"


def test_get_latest_for_target(repository: DiagnosticRepository) -> None:
    repository.save(
        _make_result(
            "diag-1", DiagnosticState.HEALTHY, target_device_id="lab-gateway-1", started_at=datetime(2026, 7, 9, 10, 0, 0)
        )
    )
    repository.save(
        _make_result(
            "diag-2", DiagnosticState.WARNING, target_device_id="lab-gateway-1", started_at=datetime(2026, 7, 9, 11, 0, 0)
        )
    )
    repository.save(
        _make_result(
            "diag-3", DiagnosticState.CRITICAL, target_device_id="lab-gateway-2", started_at=datetime(2026, 7, 9, 12, 0, 0)
        )
    )

    latest = repository.get_latest_for_target("lab-gateway-1")

    assert latest is not None
    assert latest.diagnostic_id == "diag-2"


def test_get_latest_for_target_missing_returns_none(repository: DiagnosticRepository) -> None:
    assert repository.get_latest_for_target("no-existe") is None


def test_get_by_diagnostic_id(repository: DiagnosticRepository) -> None:
    repository.save(_make_result("diag-1", DiagnosticState.WARNING))
    record = repository.get_by_diagnostic_id("diag-1")
    assert record is not None
    assert record.state == DiagnosticState.WARNING.value


def test_filter_by_state(repository: DiagnosticRepository) -> None:
    repository.save(_make_result("diag-1", DiagnosticState.HEALTHY))
    repository.save(_make_result("diag-2", DiagnosticState.CRITICAL))
    records = repository.list_all(state=DiagnosticState.CRITICAL.value)
    assert [r.diagnostic_id for r in records] == ["diag-2"]


def test_delete_by_diagnostic_id(repository: DiagnosticRepository) -> None:
    repository.save(_make_result("diag-1", DiagnosticState.HEALTHY))
    repository.delete_by_diagnostic_id("diag-1")
    assert repository.list_all() == []


def test_clear_all(repository: DiagnosticRepository) -> None:
    repository.save(_make_result("diag-1", DiagnosticState.HEALTHY))
    repository.save(_make_result("diag-2", DiagnosticState.WARNING))
    repository.clear_all()
    assert repository.list_all() == []


def test_stats(repository: DiagnosticRepository) -> None:
    repository.save(_make_result("diag-1", DiagnosticState.HEALTHY, started_at=datetime(2026, 7, 9, 10, 0, 0)))
    repository.save(_make_result("diag-2", DiagnosticState.WARNING, started_at=datetime(2026, 7, 9, 10, 5, 0)))
    repository.save(_make_result("diag-3", DiagnosticState.CRITICAL, started_at=datetime(2026, 7, 9, 10, 10, 0)))

    stats = repository.stats()

    assert stats["total"] == 3
    assert stats["healthy"] == 1
    assert stats["warning"] == 1
    assert stats["degraded_or_critical"] == 1
    assert stats["latest"].diagnostic_id == "diag-3"
