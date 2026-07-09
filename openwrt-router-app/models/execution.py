from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ExecutionStatus(str, Enum):
    CREATED = "CREATED"
    CONNECTING = "CONNECTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class ExecutionResult(BaseModel):
    """Structured outcome of a single command execution. Never include credentials here."""

    execution_id: str
    command_id: str
    command_name: str
    category: str
    host: str
    port: int
    username: str
    command: str
    status: ExecutionStatus
    exit_code: int | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    stdout: str = ""
    stderr: str = ""
    parsed_data: dict[str, Any] | None = None
    user_message: str
    technical_message: str | None = None
