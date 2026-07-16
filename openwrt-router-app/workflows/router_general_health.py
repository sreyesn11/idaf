from __future__ import annotations

from core.command_service import CommandService
from core.execution_service import ExecutionService
from diagnostics.models import RouterDiagnosticResult
from diagnostics.router_health_service import RouterHealthService
from diagnostics.thresholds import load_router_general_health_thresholds
from events.event_repository import EventRepository
from models.connection import ConnectionConfig
from repositories.diagnostic_repository import DiagnosticRepository
from repositories.execution_repository import ExecutionRepository


def run_router_general_health(
    connection: ConnectionConfig,
    device_id: int | None = None,
    target_device_id: str | None = None,
    command_service: CommandService | None = None,
    execution_service: ExecutionService | None = None,
    diagnostic_repository: DiagnosticRepository | None = None,
    event_repository: EventRepository | None = None,
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
        event_repository=event_repository or EventRepository(),
    )
    return service.run(connection, device_id=device_id, target_device_id=target_device_id)
