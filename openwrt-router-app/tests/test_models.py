from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.command import CommandDefinition, ParserType
from models.connection import ConnectionConfig, HostKeyPolicy
from models.execution import ExecutionResult, ExecutionStatus


def test_connection_config_masks_password_in_repr() -> None:
    config = ConnectionConfig(host="192.168.1.1", username="root", password="secreto123")
    assert "secreto123" not in repr(config)
    assert "secreto123" not in str(config)


def test_connection_config_rejects_blank_host() -> None:
    with pytest.raises(ValidationError):
        ConnectionConfig(host="   ", username="root", password="secreto123")


def test_connection_config_defaults() -> None:
    config = ConnectionConfig(host="192.168.1.1", username="root", password="x")
    assert config.port == 22
    assert config.timeout == 10
    assert config.host_key_policy == HostKeyPolicy.AUTO


def test_command_definition_requires_valid_parser() -> None:
    with pytest.raises(ValidationError):
        CommandDefinition(
            id="test",
            name="Test",
            description="",
            command="echo test",
            parser="not_a_parser",
            category="sistema",
        )


def test_command_definition_valid() -> None:
    command = CommandDefinition(
        id="get_uptime",
        name="Tiempo de actividad",
        description="",
        command="uptime",
        parser=ParserType.UPTIME,
        category="sistema",
    )
    assert command.enabled is True
    assert command.timeout == 10


def test_execution_result_requires_status() -> None:
    with pytest.raises(ValidationError):
        ExecutionResult(
            execution_id="exec-1",
            command_id="get_uptime",
            command_name="Tiempo de actividad",
            category="sistema",
            host="192.168.1.1",
            port=22,
            username="root",
            command="uptime",
            started_at="2026-07-08T20:15:00-05:00",
            user_message="ok",
        )


def test_execution_result_valid() -> None:
    result = ExecutionResult(
        execution_id="exec-1",
        command_id="get_uptime",
        command_name="Tiempo de actividad",
        category="sistema",
        host="192.168.1.1",
        port=22,
        username="root",
        command="uptime",
        status=ExecutionStatus.COMPLETED,
        started_at="2026-07-08T20:15:00-05:00",
        user_message="ok",
    )
    assert result.status == ExecutionStatus.COMPLETED
