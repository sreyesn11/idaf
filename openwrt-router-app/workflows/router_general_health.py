from __future__ import annotations

from core.command_service import CommandService
from core.execution_service import ExecutionService
from diagnostics.models import RouterDiagnosticResult
from diagnostics.router_health_service import RouterHealthService
from diagnostics.thresholds import load_router_general_health_thresholds
from models.connection import ConnectionConfig
from repositories.diagnostic_repository import DiagnosticRepository
from repositories.execution_repository import ExecutionRepository


def run_router_general_health(
    connection: ConnectionConfig,
    command_service: CommandService | None = None,
    execution_service: ExecutionService | None = None,
    diagnostic_repository: DiagnosticRepository | None = None,
) -> RouterDiagnosticResult:
    """Entry point for the 'Router General Health' diagnostic.

    Wires up CommandService, ExecutionService and DiagnosticRepository and
    delegates the check-by-check logic to RouterHealthService. No command is
    ever executed outside of the existing ExecutionService/CommandService.
    """
    thresholds = load_router_general_health_thresholds()
    service = RouterHealthService(
        command_service=command_service or CommandService(),
        execution_service=execution_service or ExecutionService(repository=ExecutionRepository()),
        diagnostic_repository=diagnostic_repository or DiagnosticRepository(),
        thresholds=thresholds,
    )
    return service.run(connection)
