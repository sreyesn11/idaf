from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from diagnostics.enums import DiagnosticState


class DiagnosticCheckResult(BaseModel):
    """Outcome of a single check within a diagnostic (e.g. memory, LAN, SSH access)."""

    check_id: str
    check_name: str
    state: DiagnosticState
    summary: str
    value: float | int | str | bool | None = None
    unit: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    evidence_execution_ids: list[str] = Field(default_factory=list)


class RouterDiagnosticResult(BaseModel):
    """Consolidated result of a full diagnostic run (e.g. Router General Health)."""

    diagnostic_id: str
    diagnostic_type: str = "router_general_health"
    target: str
    state: DiagnosticState
    summary: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    checks: list[DiagnosticCheckResult]
    evidence_execution_ids: list[str]
    warnings: list[str] = Field(default_factory=list)
