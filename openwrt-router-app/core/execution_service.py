from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from core.constants import EXECUTIONS_EVIDENCE_DIR
from core.exceptions import ParserError, RouterAppError, SSHTimeoutError
from core.ssh_client import SSHClient
from models.command import CommandDefinition
from models.connection import ConnectionConfig
from models.execution import ExecutionResult, ExecutionStatus
from parsers.base import BaseParser
from parsers.df_parser import DFParser
from parsers.free_parser import FreeParser
from parsers.json_parser import JSONParser
from parsers.lines_parser import LinesParser
from parsers.text_parser import TextParser
from parsers.uptime_parser import UptimeParser
from repositories.execution_repository import ExecutionRepository

logger = logging.getLogger(__name__)

_PARSERS: dict[str, BaseParser] = {
    "json": JSONParser(),
    "text": TextParser(),
    "lines": LinesParser(),
    "uptime": UptimeParser(),
    "free": FreeParser(),
    "df": DFParser(),
}


class ExecutionService:
    """Orchestrates SSH execution, parsing, persistence and evidence generation for one command run."""

    def __init__(self, repository: ExecutionRepository | None = None, evidence_dir: Path = EXECUTIONS_EVIDENCE_DIR) -> None:
        self._repository = repository or ExecutionRepository()
        self._evidence_dir = evidence_dir

    def run(
        self,
        connection: ConnectionConfig,
        command_def: CommandDefinition,
        device_id: int | None = None,
    ) -> ExecutionResult:
        execution_id = self._new_execution_id()
        started_at = datetime.now().astimezone()

        base_fields = dict(
            execution_id=execution_id,
            command_id=command_def.id,
            command_name=command_def.name,
            category=command_def.category,
            host=connection.host,
            port=connection.port,
            username=connection.username,
            command=command_def.command,
            started_at=started_at,
        )

        logger.info(
            "Inicio de ejecución execution_id=%s comando_id=%s host=%s usuario=%s",
            execution_id,
            command_def.id,
            connection.host,
            connection.username,
        )

        try:
            with SSHClient(connection) as client:
                output = client.execute(command_def.command, timeout=command_def.timeout)
        except RouterAppError as exc:
            return self._finalize(self._build_error_result(base_fields, exc), device_id=device_id)
        except Exception:  # noqa: BLE001 - never expose an uncontrolled exception's str() to the user
            logger.exception("Error inesperado ejecutando execution_id=%s", execution_id)
            return self._finalize(self._build_error_result(base_fields, RouterAppError()), device_id=device_id)

        finished_at = datetime.now().astimezone()
        parsed_data, status, technical_message = self._parse_output(
            command_def.parser.value, output.stdout, output.exit_code
        )

        result = ExecutionResult(
            **base_fields,
            status=status,
            exit_code=output.exit_code,
            finished_at=finished_at,
            duration_seconds=round(output.duration_seconds, 3),
            stdout=output.stdout,
            stderr=output.stderr,
            parsed_data=parsed_data,
            user_message=self._user_message_for(status),
            technical_message=technical_message,
        )
        return self._finalize(result, device_id=device_id)

    @staticmethod
    def _new_execution_id() -> str:
        today = datetime.now().strftime("%Y%m%d")
        return f"exec-{today}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _parse_output(parser_name: str, stdout: str, exit_code: int) -> tuple[dict | None, ExecutionStatus, str | None]:
        if exit_code != 0:
            return None, ExecutionStatus.FAILED, f"El comando finalizó con código de salida {exit_code}."

        parser = _PARSERS.get(parser_name)
        if parser is None:
            return None, ExecutionStatus.COMPLETED_WITH_WARNINGS, f"No hay un parser registrado para '{parser_name}'."

        try:
            parsed = parser.parse(stdout)
        except ParserError as exc:
            logger.warning("Error de parsing: %s", exc.detail or exc.friendly_message)
            return None, ExecutionStatus.COMPLETED_WITH_WARNINGS, exc.detail or exc.friendly_message
        return parsed, ExecutionStatus.COMPLETED, None

    @staticmethod
    def _build_error_result(base_fields: dict, exc: RouterAppError) -> ExecutionResult:
        status = ExecutionStatus.TIMEOUT if isinstance(exc, SSHTimeoutError) else ExecutionStatus.FAILED
        return ExecutionResult(
            **base_fields,
            status=status,
            exit_code=None,
            finished_at=datetime.now().astimezone(),
            duration_seconds=None,
            stdout="",
            stderr="",
            parsed_data=None,
            user_message=exc.friendly_message,
            technical_message=exc.detail,
        )

    @staticmethod
    def _user_message_for(status: ExecutionStatus) -> str:
        if status == ExecutionStatus.COMPLETED:
            return "Consulta ejecutada correctamente."
        if status == ExecutionStatus.COMPLETED_WITH_WARNINGS:
            return "Consulta ejecutada, pero la salida no se pudo interpretar completamente."
        return "La consulta finalizó con errores."

    def _finalize(self, result: ExecutionResult, device_id: int | None = None) -> ExecutionResult:
        evidence_path = None
        try:
            evidence_path = self._write_evidence(result)
        except OSError:
            logger.exception("No fue posible escribir la evidencia de la ejecución %s", result.execution_id)

        try:
            self._repository.save(result, evidence_path=evidence_path, device_id=device_id)
        except Exception:  # noqa: BLE001 - persistence must never hide an already-computed result
            logger.exception("No fue posible persistir la ejecución %s", result.execution_id)

        logger.info(
            "Fin de ejecución execution_id=%s estado=%s duracion=%s",
            result.execution_id,
            result.status.value,
            result.duration_seconds,
        )
        return result

    def _write_evidence(self, result: ExecutionResult) -> Path:
        started = result.started_at
        day_dir = self._evidence_dir / f"{started:%Y}" / f"{started:%m}" / f"{started:%d}"
        day_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = day_dir / f"{result.execution_id}.json"
        payload = json.loads(result.model_dump_json())
        evidence_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return evidence_path
