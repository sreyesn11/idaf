from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from models.execution import ExecutionResult, ExecutionStatus
from repositories.database import get_engine
from repositories.execution_repository import ExecutionRepository


@pytest.fixture()
def repository(tmp_path: Path) -> ExecutionRepository:
    engine = get_engine(tmp_path / "history.db")
    return ExecutionRepository(engine=engine)


def _make_result(
    execution_id: str,
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
    started_at: datetime = datetime(2026, 7, 9, 10, 0, 0),
) -> ExecutionResult:
    return ExecutionResult(
        execution_id=execution_id,
        command_id="get_system_board",
        command_name="Información general del router",
        category="sistema",
        host="192.168.1.1",
        port=22,
        username="root",
        command="ubus call system board",
        status=status,
        exit_code=0,
        started_at=started_at,
        user_message="ok",
    )


def test_save_and_list_all(repository: ExecutionRepository) -> None:
    repository.save(_make_result("exec-1"))
    records = repository.list_all()
    assert len(records) == 1
    assert records[0].execution_id == "exec-1"
    assert records[0].device_id is None


def test_save_with_device_id(repository: ExecutionRepository) -> None:
    repository.save(_make_result("exec-1"), device_id=7)
    records = repository.list_all()
    assert records[0].device_id == 7


def test_filter_by_device_id(repository: ExecutionRepository) -> None:
    repository.save(_make_result("exec-1"), device_id=1)
    repository.save(_make_result("exec-2"), device_id=2)
    records = repository.list_all(device_id=2)
    assert [r.execution_id for r in records] == ["exec-2"]


def test_get_by_execution_id(repository: ExecutionRepository) -> None:
    repository.save(_make_result("exec-1"))
    record = repository.get_by_execution_id("exec-1")
    assert record is not None
    assert record.execution_id == "exec-1"


def test_filter_by_status(repository: ExecutionRepository) -> None:
    repository.save(_make_result("exec-1", status=ExecutionStatus.COMPLETED))
    repository.save(_make_result("exec-2", status=ExecutionStatus.FAILED))
    records = repository.list_all(status=ExecutionStatus.FAILED.value)
    assert [r.execution_id for r in records] == ["exec-2"]


def test_delete_by_execution_id(repository: ExecutionRepository) -> None:
    repository.save(_make_result("exec-1"))
    repository.delete_by_execution_id("exec-1")
    assert repository.list_all() == []


def test_clear_all(repository: ExecutionRepository) -> None:
    repository.save(_make_result("exec-1"))
    repository.save(_make_result("exec-2"))
    repository.clear_all()
    assert repository.list_all() == []


def test_stats(repository: ExecutionRepository) -> None:
    repository.save(_make_result("exec-1", status=ExecutionStatus.COMPLETED))
    repository.save(_make_result("exec-2", status=ExecutionStatus.FAILED))

    stats = repository.stats()

    assert stats["total"] == 2
    assert stats["successful"] == 1
    assert stats["failed"] == 1
