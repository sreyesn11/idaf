from __future__ import annotations

from enum import Enum


class DiagnosticState(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"
