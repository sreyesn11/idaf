from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.exceptions import SSHConnectionError
from core.execution_service import ExecutionService
from core.ssh_client import CommandOutput
from models.command import CommandDefinition, ParserType
from models.connection import ConnectionConfig
from models.execution import ExecutionStatus
from repositories.database import get_engine
from repositories.execution_repository import ExecutionRepository


@pytest.fixture()
def connection() -> ConnectionConfig:
    return ConnectionConfig(host="192.168.1.1", username="root", password="secreto")


@pytest.fixture()
def command() -> CommandDefinition:
    return CommandDefinition(
        id="get_system_board",
        name="Información general del router",
        description="",
        command="ubus call system board",
        parser=ParserType.JSON,
        category="sistema",
        timeout=10,
    )


@pytest.fixture()
def repository(tmp_path: Path) -> ExecutionRepository:
    engine = get_engine(tmp_path / "history.db")
    return ExecutionRepository(engine=engine)


def _fake_ssh_client_factory(output: CommandOutput) -> MagicMock:
    fake_client = MagicMock()
    fake_client.execute.return_value = output
    fake_client.__enter__.return_value = fake_client
    fake_client.__exit__.return_value = False
    return MagicMock(return_value=fake_client)


def test_successful_execution_is_completed(monkeypatch, connection, command, repository, tmp_path) -> None:
    output = CommandOutput(stdout='{"hostname": "OpenWrt"}', stderr="", exit_code=0, duration_seconds=0.5)
    monkeypatch.setattr("core.execution_service.SSHClient", _fake_ssh_client_factory(output))

    service = ExecutionService(repository=repository, evidence_dir=tmp_path / "evidence")
    result = service.run(connection, command)

    assert result.status == ExecutionStatus.COMPLETED
    assert result.parsed_data == {"hostname": "OpenWrt"}
    assert result.exit_code == 0

    records = repository.list_all()
    assert len(records) == 1
    assert records[0].execution_id == result.execution_id


def test_nonzero_exit_code_is_failed(monkeypatch, connection, command, repository, tmp_path) -> None:
    output = CommandOutput(stdout="", stderr="not found", exit_code=1, duration_seconds=0.1)
    monkeypatch.setattr("core.execution_service.SSHClient", _fake_ssh_client_factory(output))

    service = ExecutionService(repository=repository, evidence_dir=tmp_path / "evidence")
    result = service.run(connection, command)

    assert result.status == ExecutionStatus.FAILED
    assert result.exit_code == 1


def test_invalid_json_is_completed_with_warnings(monkeypatch, connection, command, repository, tmp_path) -> None:
    output = CommandOutput(stdout="not json", stderr="", exit_code=0, duration_seconds=0.2)
    monkeypatch.setattr("core.execution_service.SSHClient", _fake_ssh_client_factory(output))

    service = ExecutionService(repository=repository, evidence_dir=tmp_path / "evidence")
    result = service.run(connection, command)

    assert result.status == ExecutionStatus.COMPLETED_WITH_WARNINGS
    assert result.parsed_data is None
    assert result.stdout == "not json"


def test_connection_error_is_failed_without_real_ssh(monkeypatch, connection, command, repository, tmp_path) -> None:
    def _raise(*args, **kwargs):
        raise SSHConnectionError("host inalcanzable")

    monkeypatch.setattr("core.execution_service.SSHClient", _raise)

    service = ExecutionService(repository=repository, evidence_dir=tmp_path / "evidence")
    result = service.run(connection, command)

    assert result.status == ExecutionStatus.FAILED
    assert result.exit_code is None
    assert "inalcanzable" in (result.technical_message or "")


def test_evidence_file_is_written(monkeypatch, connection, command, repository, tmp_path) -> None:
    output = CommandOutput(stdout='{"hostname": "OpenWrt"}', stderr="", exit_code=0, duration_seconds=0.5)
    monkeypatch.setattr("core.execution_service.SSHClient", _fake_ssh_client_factory(output))

    evidence_dir = tmp_path / "evidence"
    service = ExecutionService(repository=repository, evidence_dir=evidence_dir)
    result = service.run(connection, command)

    expected_path = (
        evidence_dir
        / f"{result.started_at:%Y}"
        / f"{result.started_at:%m}"
        / f"{result.started_at:%d}"
        / f"{result.execution_id}.json"
    )
    assert expected_path.exists()
