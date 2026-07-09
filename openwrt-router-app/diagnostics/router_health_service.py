from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from core.command_service import CommandService
from core.constants import CONNECTION_TEST_COMMAND, DIAGNOSTICS_EVIDENCE_DIR
from core.exceptions import RouterAppError
from core.execution_service import ExecutionService
from core.ssh_client import SSHClient
from diagnostics.consolidator import consolidate
from diagnostics.models import DiagnosticCheckResult, RouterDiagnosticResult
from diagnostics.rules import (
    check_identity,
    check_ipv6,
    check_lan,
    check_memory,
    check_ssh,
    check_storage,
    check_uptime,
    check_wan,
    check_wifi,
)
from diagnostics.thresholds import RouterGeneralHealthThresholds
from models.connection import ConnectionConfig
from models.execution import ExecutionResult
from repositories.diagnostic_repository import DiagnosticRepository

logger = logging.getLogger(__name__)

_BASE_REQUIRED_CHECK_IDS = {"ssh", "identity", "uptime", "memory", "storage", "lan"}

_DIAGNOSTIC_COMMAND_IDS = [
    "get_system_board",
    "get_uptime",
    "get_memory",
    "get_disk_usage",
    "get_lan_status",
    "get_wan_status",
    "get_ipv6_interfaces",
    "get_wireless_status",
    "get_cpu_cores",
]


class RouterHealthService:
    """Runs the 'Router General Health' diagnostic: SSH probe + a fixed set of commands,
    evaluated through diagnostics.rules and consolidated via diagnostics.consolidator.
    Every command still goes through the existing ExecutionService/CommandService.
    """

    def __init__(
        self,
        command_service: CommandService,
        execution_service: ExecutionService,
        diagnostic_repository: DiagnosticRepository,
        thresholds: RouterGeneralHealthThresholds,
        evidence_dir: Path = DIAGNOSTICS_EVIDENCE_DIR,
    ) -> None:
        self._command_service = command_service
        self._execution_service = execution_service
        self._diagnostic_repository = diagnostic_repository
        self._thresholds = thresholds
        self._evidence_dir = evidence_dir

    def run(self, connection: ConnectionConfig) -> RouterDiagnosticResult:
        diagnostic_id = self._new_diagnostic_id()
        started_at = datetime.now().astimezone()
        warnings: list[str] = []
        evidence_execution_ids: list[str] = []

        ssh_check, ssh_ok = self._check_ssh_access(connection)
        checks: list[DiagnosticCheckResult] = [ssh_check]

        if ssh_ok:
            execution_results = self._run_commands(connection, warnings)
            evidence_execution_ids = [r.execution_id for r in execution_results.values()]

            checks.append(check_identity(execution_results.get("get_system_board")))
            checks.append(
                check_uptime(
                    execution_results.get("get_uptime"),
                    execution_results.get("get_cpu_cores"),
                    self._thresholds.uptime,
                    self._thresholds.load,
                )
            )
            checks.append(check_memory(execution_results.get("get_memory"), self._thresholds.memory))
            checks.append(check_storage(execution_results.get("get_disk_usage"), self._thresholds.storage))
            checks.append(check_lan(execution_results.get("get_lan_status")))
            checks.append(check_wan(execution_results.get("get_wan_status"), self._thresholds.wan.required))
            checks.append(check_ipv6(execution_results.get("get_ipv6_interfaces"), self._thresholds.ipv6.required))
            checks.append(check_wifi(execution_results.get("get_wireless_status"), self._thresholds.wifi.required))
        else:
            warnings.append("No se ejecutaron los demás chequeos porque el router no es alcanzable por SSH.")

        required_check_ids = set(_BASE_REQUIRED_CHECK_IDS)
        if self._thresholds.wan.required:
            required_check_ids.add("wan")
        if self._thresholds.ipv6.required:
            required_check_ids.add("ipv6")
        if self._thresholds.wifi.required:
            required_check_ids.add("wifi")

        state, summary = consolidate(checks, required_check_ids)
        finished_at = datetime.now().astimezone()

        result = RouterDiagnosticResult(
            diagnostic_id=diagnostic_id,
            target=connection.host,
            state=state,
            summary=summary,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=round((finished_at - started_at).total_seconds(), 3),
            checks=checks,
            evidence_execution_ids=evidence_execution_ids,
            warnings=warnings,
        )
        return self._finalize(result)

    def _run_commands(self, connection: ConnectionConfig, warnings: list[str]) -> dict[str, ExecutionResult]:
        execution_results: dict[str, ExecutionResult] = {}
        for command_id in _DIAGNOSTIC_COMMAND_IDS:
            try:
                command = self._command_service.get_by_id(command_id)
            except RouterAppError as exc:
                warnings.append(f"El comando '{command_id}' no está disponible: {exc.friendly_message}")
                continue
            execution_results[command_id] = self._execution_service.run(connection, command)
        return execution_results

    def _check_ssh_access(self, connection: ConnectionConfig) -> tuple[DiagnosticCheckResult, bool]:
        started = time.monotonic()
        try:
            with SSHClient(connection) as client:
                client.execute(CONNECTION_TEST_COMMAND, timeout=connection.timeout)
            elapsed_ms = (time.monotonic() - started) * 1000
        except RouterAppError as exc:
            return check_ssh(elapsed_ms=None, error=exc, thresholds=self._thresholds.ssh), False
        except Exception:  # noqa: BLE001 - never expose an uncontrolled exception's str() to the user
            logger.exception("Error inesperado validando acceso SSH")
            return check_ssh(elapsed_ms=None, error=RouterAppError(), thresholds=self._thresholds.ssh), False
        return check_ssh(elapsed_ms=elapsed_ms, error=None, thresholds=self._thresholds.ssh), True

    @staticmethod
    def _new_diagnostic_id() -> str:
        today = datetime.now().strftime("%Y%m%d")
        return f"diag-{today}-{uuid.uuid4().hex[:8]}"

    def _finalize(self, result: RouterDiagnosticResult) -> RouterDiagnosticResult:
        evidence_path = None
        try:
            evidence_path = self._write_evidence(result)
        except OSError:
            logger.exception("No fue posible escribir la evidencia del diagnóstico %s", result.diagnostic_id)

        try:
            self._diagnostic_repository.save(result, evidence_path=evidence_path)
        except Exception:  # noqa: BLE001 - persistence must never hide an already-computed result
            logger.exception("No fue posible persistir el diagnóstico %s", result.diagnostic_id)

        logger.info(
            "Diagnóstico finalizado diagnostic_id=%s estado=%s duracion=%s",
            result.diagnostic_id,
            result.state.value,
            result.duration_seconds,
        )
        return result

    def _write_evidence(self, result: RouterDiagnosticResult) -> Path:
        started = result.started_at
        day_dir = self._evidence_dir / f"{started:%Y}" / f"{started:%m}" / f"{started:%d}"
        day_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = day_dir / f"{result.diagnostic_id}.json"
        payload = json.loads(result.model_dump_json())
        evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return evidence_path
