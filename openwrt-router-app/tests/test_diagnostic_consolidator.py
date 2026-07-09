from __future__ import annotations

from diagnostics.consolidator import consolidate
from diagnostics.enums import DiagnosticState
from diagnostics.models import DiagnosticCheckResult

_REQUIRED = {"ssh", "identity", "uptime", "memory", "storage", "lan"}


def _check(check_id: str, state: DiagnosticState) -> DiagnosticCheckResult:
    return DiagnosticCheckResult(check_id=check_id, check_name=check_id, state=state, summary="")


def test_all_healthy_is_healthy() -> None:
    checks = [_check(cid, DiagnosticState.HEALTHY) for cid in _REQUIRED]
    state, _ = consolidate(checks, _REQUIRED)
    assert state == DiagnosticState.HEALTHY


def test_one_warning_is_warning() -> None:
    checks = [_check(cid, DiagnosticState.HEALTHY) for cid in _REQUIRED]
    checks.append(_check("wan", DiagnosticState.WARNING))
    state, _ = consolidate(checks, _REQUIRED)
    assert state == DiagnosticState.WARNING


def test_one_required_degraded_is_degraded() -> None:
    checks = [_check(cid, DiagnosticState.HEALTHY) for cid in _REQUIRED if cid != "lan"]
    checks.append(_check("lan", DiagnosticState.DEGRADED))
    state, _ = consolidate(checks, _REQUIRED)
    assert state == DiagnosticState.DEGRADED


def test_one_critical_is_critical() -> None:
    checks = [_check(cid, DiagnosticState.HEALTHY) for cid in _REQUIRED if cid != "memory"]
    checks.append(_check("memory", DiagnosticState.CRITICAL))
    state, _ = consolidate(checks, _REQUIRED)
    assert state == DiagnosticState.CRITICAL


def test_ssh_unreachable_is_unreachable_regardless_of_other_checks() -> None:
    checks = [_check("ssh", DiagnosticState.UNREACHABLE)]
    state, summary = consolidate(checks, _REQUIRED)
    assert state == DiagnosticState.UNREACHABLE
    assert "SSH" in summary
