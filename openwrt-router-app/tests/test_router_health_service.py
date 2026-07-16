from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from diagnostics.enums import DiagnosticState
from diagnostics.router_health_service import RouterHealthService
from diagnostics.thresholds import load_router_general_health_thresholds
from events.event_repository import EventRepository
from models.connection import ConnectionConfig
from models.execution import ExecutionResult, ExecutionStatus
from repositories.database import get_engine
from repositories.diagnostic_repository import DiagnosticRepository


@pytest.fixture()
def connection() -> ConnectionConfig:
    return ConnectionConfig(host="192.168.1.1", username="root", password="secreto")


@pytest.fixture()
def thresholds():
    return load_router_general_health_thresholds()


@pytest.fixture()
def diagnostic_repository(tmp_path: Path) -> DiagnosticRepository:
    engine = get_engine(tmp_path / "history.db")
    return DiagnosticRepository(engine=engine)


@pytest.fixture()
def event_repository(tmp_path: Path) -> EventRepository:
    engine = get_engine(tmp_path / "history.db")
    return EventRepository(engine=engine)


def _completed_execution(command_id: str, parsed_data: dict) -> ExecutionResult:
    from datetime import datetime

    return ExecutionResult(
        execution_id=f"exec-{command_id}",
        command_id=command_id,
        command_name=command_id,
        category="sistema",
        host="192.168.1.1",
        port=22,
        username="root",
        command=command_id,
        status=ExecutionStatus.COMPLETED,
        exit_code=0,
        started_at=datetime(2026, 7, 9, 10, 0, 0),
        parsed_data=parsed_data,
        user_message="ok",
    )


_HEALTHY_PARSED_DATA = {
    "get_system_board": {"hostname": "idaf-openwrt", "model": "OpenWrt One", "kernel": "5.15", "release": "23.05"},
    "get_uptime": {"time": "10:00:00", "uptime": "3 days, 2:00", "users": 1, "load_1m": 0.1, "load_5m": 0.1, "load_15m": 0.1},
    "get_memory": {"total": 128000, "used": 32000, "free": 96000},
    "get_disk_usage": {"filesystems": [{"mountpoint": "/", "use_percent": "40", "size": "100M", "used": "40M", "available": "60M"}]},
    "get_lan_status": {"up": True, "l3_device": "br-lan", "ipv4-address": [{"address": "192.168.1.1"}]},
    "get_wan_status": {"up": True},
    "get_ipv6_interfaces": {"raw_text": "inet6 2001:db8::1/64 scope global"},
    "get_wireless_status": {"radio0": {"up": True, "disabled": False}},
    "get_cpu_cores": {"raw_text": "4"},
}


def _make_command_service_stub():
    from models.command import CommandDefinition, ParserType

    parser_by_id = {
        "get_system_board": ParserType.JSON,
        "get_uptime": ParserType.UPTIME,
        "get_memory": ParserType.FREE,
        "get_disk_usage": ParserType.DF,
        "get_lan_status": ParserType.JSON,
        "get_wan_status": ParserType.JSON,
        "get_ipv6_interfaces": ParserType.TEXT,
        "get_wireless_status": ParserType.JSON,
        "get_cpu_cores": ParserType.TEXT,
    }
    stub = MagicMock()
    stub.get_by_id.side_effect = lambda command_id: CommandDefinition(
        id=command_id,
        name=command_id,
        description="",
        command=command_id,
        parser=parser_by_id[command_id],
        category="sistema",
    )
    return stub


def _make_execution_service_stub(parsed_data_by_command: dict[str, dict]):
    stub = MagicMock()
    stub.run.side_effect = lambda connection, command, device_id=None: _completed_execution(
        command.id, parsed_data_by_command[command.id]
    )
    return stub


def _make_ssh_probe_ok(monkeypatch):
    fake_client = MagicMock()
    fake_client.execute.return_value = MagicMock(stdout="IDAF_ROUTER_CONNECTION_OK")
    fake_client.__enter__.return_value = fake_client
    fake_client.__exit__.return_value = False
    monkeypatch.setattr("diagnostics.router_health_service.SSHClient", MagicMock(return_value=fake_client))


def test_healthy_router_produces_healthy_diagnostic(monkeypatch, connection, thresholds, diagnostic_repository, event_repository, tmp_path) -> None:
    _make_ssh_probe_ok(monkeypatch)
    service = RouterHealthService(
        command_service=_make_command_service_stub(),
        execution_service=_make_execution_service_stub(_HEALTHY_PARSED_DATA),
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=tmp_path / "evidence",
    )

    result = service.run(connection)

    assert result.state == DiagnosticState.HEALTHY
    assert len(result.checks) == 9
    assert diagnostic_repository.list_all()


def test_ssh_unreachable_short_circuits_other_checks(monkeypatch, connection, thresholds, diagnostic_repository, event_repository, tmp_path) -> None:
    from core.exceptions import SSHConnectionError

    monkeypatch.setattr(
        "diagnostics.router_health_service.SSHClient",
        MagicMock(side_effect=SSHConnectionError("host inalcanzable")),
    )
    execution_service = _make_execution_service_stub(_HEALTHY_PARSED_DATA)
    service = RouterHealthService(
        command_service=_make_command_service_stub(),
        execution_service=execution_service,
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=tmp_path / "evidence",
    )

    result = service.run(connection)

    assert result.state == DiagnosticState.UNREACHABLE
    execution_service.run.assert_not_called()


def test_missing_command_is_reported_as_warning_not_a_crash(monkeypatch, connection, thresholds, diagnostic_repository, event_repository, tmp_path) -> None:
    from core.exceptions import CommandNotAllowedError

    _make_ssh_probe_ok(monkeypatch)
    command_service = _make_command_service_stub()
    command_service.get_by_id.side_effect = CommandNotAllowedError("no disponible")
    service = RouterHealthService(
        command_service=command_service,
        execution_service=_make_execution_service_stub(_HEALTHY_PARSED_DATA),
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=tmp_path / "evidence",
    )

    result = service.run(connection)

    assert result.warnings
    assert all(check.state == DiagnosticState.UNKNOWN for check in result.checks if check.check_id != "ssh")


def test_parser_failure_yields_unknown_check_not_a_crash(monkeypatch, connection, thresholds, diagnostic_repository, event_repository, tmp_path) -> None:
    _make_ssh_probe_ok(monkeypatch)
    broken_data = dict(_HEALTHY_PARSED_DATA)
    broken_data["get_memory"] = {}  # no 'total'/'used' -> memory rule can't compute a percentage
    service = RouterHealthService(
        command_service=_make_command_service_stub(),
        execution_service=_make_execution_service_stub(broken_data),
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=tmp_path / "evidence",
    )

    result = service.run(connection)

    memory_check = next(c for c in result.checks if c.check_id == "memory")
    assert memory_check.state == DiagnosticState.UNKNOWN


def test_persistence_failure_still_returns_result(monkeypatch, connection, thresholds, diagnostic_repository, event_repository, tmp_path) -> None:
    _make_ssh_probe_ok(monkeypatch)
    diagnostic_repository.save = MagicMock(side_effect=RuntimeError("disco lleno"))
    service = RouterHealthService(
        command_service=_make_command_service_stub(),
        execution_service=_make_execution_service_stub(_HEALTHY_PARSED_DATA),
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=tmp_path / "evidence",
    )

    result = service.run(connection)

    assert result.state == DiagnosticState.HEALTHY


def test_evidence_write_failure_still_returns_result(monkeypatch, connection, thresholds, diagnostic_repository, event_repository, tmp_path) -> None:
    _make_ssh_probe_ok(monkeypatch)
    # A regular file where a directory is expected makes mkdir(parents=True) raise OSError.
    blocker_file = tmp_path / "blocker"
    blocker_file.write_text("not a directory", encoding="utf-8")
    service = RouterHealthService(
        command_service=_make_command_service_stub(),
        execution_service=_make_execution_service_stub(_HEALTHY_PARSED_DATA),
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=blocker_file / "diagnostics",
    )

    result = service.run(connection)

    assert result.state == DiagnosticState.HEALTHY
    assert diagnostic_repository.list_all()


def test_state_change_between_runs_creates_event(monkeypatch, connection, thresholds, diagnostic_repository, event_repository, tmp_path) -> None:
    _make_ssh_probe_ok(monkeypatch)
    service = RouterHealthService(
        command_service=_make_command_service_stub(),
        execution_service=_make_execution_service_stub(_HEALTHY_PARSED_DATA),
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=tmp_path / "evidence",
    )
    first = service.run(connection)
    assert first.state == DiagnosticState.HEALTHY
    assert event_repository.list_all() == []

    critical_data = dict(_HEALTHY_PARSED_DATA)
    critical_data["get_memory"] = {"total": 100000, "used": 95000, "free": 5000}
    service_critical = RouterHealthService(
        command_service=_make_command_service_stub(),
        execution_service=_make_execution_service_stub(critical_data),
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=tmp_path / "evidence",
    )
    second = service_critical.run(connection)

    assert second.state == DiagnosticState.CRITICAL
    events = event_repository.list_all()
    assert len(events) == 1
    assert events[0].from_state == DiagnosticState.HEALTHY.value
    assert events[0].to_state == DiagnosticState.CRITICAL.value
    assert events[0].target_device_id == first.target_device_id


def test_unchanged_state_between_runs_creates_no_event(monkeypatch, connection, thresholds, diagnostic_repository, event_repository, tmp_path) -> None:
    _make_ssh_probe_ok(monkeypatch)
    service = RouterHealthService(
        command_service=_make_command_service_stub(),
        execution_service=_make_execution_service_stub(_HEALTHY_PARSED_DATA),
        diagnostic_repository=diagnostic_repository,
        event_repository=event_repository,
        thresholds=thresholds,
        evidence_dir=tmp_path / "evidence",
    )
    service.run(connection)
    service.run(connection)

    assert event_repository.list_all() == []
