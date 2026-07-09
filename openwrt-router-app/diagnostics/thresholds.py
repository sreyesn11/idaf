from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from core.constants import DIAGNOSTIC_THRESHOLDS_FILE
from core.exceptions import DiagnosticConfigurationError


class SSHThresholds(BaseModel):
    warning_latency_ms: float
    critical_latency_ms: float


class MemoryThresholds(BaseModel):
    warning_percent: float
    critical_percent: float


class StorageThresholds(BaseModel):
    warning_percent: float
    critical_percent: float


class LoadThresholds(BaseModel):
    warning_ratio_per_core: float
    critical_ratio_per_core: float


class UptimeThresholds(BaseModel):
    warning_seconds: float


class RequirementThresholds(BaseModel):
    required: bool = False


class RouterGeneralHealthThresholds(BaseModel):
    ssh: SSHThresholds
    memory: MemoryThresholds
    storage: StorageThresholds
    load: LoadThresholds
    uptime: UptimeThresholds
    wan: RequirementThresholds
    ipv6: RequirementThresholds
    wifi: RequirementThresholds


class DiagnosticThresholds(BaseModel):
    router_general_health: RouterGeneralHealthThresholds


def load_router_general_health_thresholds(
    thresholds_file: Path = DIAGNOSTIC_THRESHOLDS_FILE,
) -> RouterGeneralHealthThresholds:
    if not thresholds_file.exists():
        raise DiagnosticConfigurationError(f"No se encontró el archivo de umbrales: {thresholds_file}")

    with thresholds_file.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    try:
        return DiagnosticThresholds.model_validate(raw).router_general_health
    except Exception as exc:  # pydantic.ValidationError
        raise DiagnosticConfigurationError(
            f"El archivo de umbrales {thresholds_file.name} no es válido: {exc}"
        ) from exc
