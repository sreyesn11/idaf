from __future__ import annotations

from datetime import datetime

import pytest

from diagnostics.enums import DiagnosticState
from diagnostics.rules import (
    check_ipv6,
    check_lan,
    check_memory,
    check_ssh,
    check_storage,
    check_wan,
)
from diagnostics.thresholds import MemoryThresholds, SSHThresholds, StorageThresholds
from models.execution import ExecutionResult, ExecutionStatus


def _completed_result(command_id: str, parsed_data: dict) -> ExecutionResult:
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


@pytest.fixture()
def memory_thresholds() -> MemoryThresholds:
    return MemoryThresholds(warning_percent=75, critical_percent=90)


@pytest.fixture()
def storage_thresholds() -> StorageThresholds:
    return StorageThresholds(warning_percent=80, critical_percent=90)


@pytest.fixture()
def ssh_thresholds() -> SSHThresholds:
    return SSHThresholds(warning_latency_ms=800, critical_latency_ms=2000)


def test_memory_50_percent_is_healthy(memory_thresholds) -> None:
    result = _completed_result("get_memory", {"total": 1000, "used": 500})
    check = check_memory(result, memory_thresholds)
    assert check.state == DiagnosticState.HEALTHY


def test_memory_80_percent_is_warning(memory_thresholds) -> None:
    result = _completed_result("get_memory", {"total": 1000, "used": 800})
    check = check_memory(result, memory_thresholds)
    assert check.state == DiagnosticState.WARNING


def test_memory_95_percent_is_critical(memory_thresholds) -> None:
    result = _completed_result("get_memory", {"total": 1000, "used": 950})
    check = check_memory(result, memory_thresholds)
    assert check.state == DiagnosticState.CRITICAL


def test_storage_70_percent_is_healthy(storage_thresholds) -> None:
    result = _completed_result(
        "get_disk_usage",
        {"filesystems": [{"mountpoint": "/", "use_percent": "70", "size": "100M", "used": "70M", "available": "30M"}]},
    )
    check = check_storage(result, storage_thresholds)
    assert check.state == DiagnosticState.HEALTHY


def test_storage_85_percent_is_warning(storage_thresholds) -> None:
    result = _completed_result(
        "get_disk_usage",
        {"filesystems": [{"mountpoint": "/", "use_percent": "85", "size": "100M", "used": "85M", "available": "15M"}]},
    )
    check = check_storage(result, storage_thresholds)
    assert check.state == DiagnosticState.WARNING


def test_storage_95_percent_is_critical(storage_thresholds) -> None:
    result = _completed_result(
        "get_disk_usage",
        {"filesystems": [{"mountpoint": "/", "use_percent": "95", "size": "100M", "used": "95M", "available": "5M"}]},
    )
    check = check_storage(result, storage_thresholds)
    assert check.state == DiagnosticState.CRITICAL


def test_wan_down_not_required_is_warning() -> None:
    result = _completed_result("get_wan_status", {"up": False})
    check = check_wan(result, required=False)
    assert check.state == DiagnosticState.WARNING


def test_wan_down_required_is_degraded() -> None:
    result = _completed_result("get_wan_status", {"up": False})
    check = check_wan(result, required=True)
    assert check.state == DiagnosticState.DEGRADED


def test_lan_down_is_degraded() -> None:
    result = _completed_result("get_lan_status", {"up": False})
    check = check_lan(result)
    assert check.state == DiagnosticState.DEGRADED


def test_ssh_failed_is_unreachable(ssh_thresholds) -> None:
    from core.exceptions import SSHConnectionError

    check = check_ssh(elapsed_ms=None, error=SSHConnectionError("host inalcanzable"), thresholds=ssh_thresholds)
    assert check.state == DiagnosticState.UNREACHABLE


def test_ssh_low_latency_is_healthy(ssh_thresholds) -> None:
    check = check_ssh(elapsed_ms=100, error=None, thresholds=ssh_thresholds)
    assert check.state == DiagnosticState.HEALTHY


def test_ssh_high_latency_is_degraded(ssh_thresholds) -> None:
    check = check_ssh(elapsed_ms=3000, error=None, thresholds=ssh_thresholds)
    assert check.state == DiagnosticState.DEGRADED


def test_ipv6_loopback_only_is_not_treated_as_global() -> None:
    # ::1 scope host (loopback) is always present and must not count as a global/ULA address.
    result = _completed_result("get_ipv6_interfaces", {"raw_text": "    inet6 ::1/128 scope host\n"})
    check = check_ipv6(result, required=False)
    assert check.state == DiagnosticState.WARNING


def test_ipv6_link_local_only_is_warning() -> None:
    result = _completed_result("get_ipv6_interfaces", {"raw_text": "    inet6 fe80::1/64 scope link\n"})
    check = check_ipv6(result, required=False)
    assert check.state == DiagnosticState.WARNING


def test_ipv6_global_address_is_healthy() -> None:
    result = _completed_result(
        "get_ipv6_interfaces",
        {"raw_text": "    inet6 ::1/128 scope host\n    inet6 2001:db8::1/64 scope global\n"},
    )
    check = check_ipv6(result, required=False)
    assert check.state == DiagnosticState.HEALTHY
