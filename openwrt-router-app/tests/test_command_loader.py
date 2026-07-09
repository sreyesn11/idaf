from __future__ import annotations

import textwrap

import pytest

from core.command_service import CommandService
from core.exceptions import CommandNotAllowedError

SAMPLE_YAML = textwrap.dedent(
    """
    commands:
      - id: get_system_board
        name: Información general del router
        description: Obtiene modelo, hostname, kernel y versión de OpenWrt.
        command: ubus call system board
        parser: json
        category: sistema
        timeout: 10
        enabled: true

      - id: get_uptime
        name: Tiempo de actividad
        description: Consulta el tiempo de actividad y carga del router.
        command: uptime
        parser: uptime
        category: sistema
        timeout: 10
        enabled: true

      - id: disabled_command
        name: Comando deshabilitado
        description: No debe aparecer en la lista.
        command: echo nunca
        parser: text
        category: sistema
        timeout: 10
        enabled: false
    """
)


@pytest.fixture()
def command_service(tmp_path) -> CommandService:
    commands_file = tmp_path / "commands.yaml"
    commands_file.write_text(SAMPLE_YAML, encoding="utf-8")
    return CommandService(commands_file=commands_file)


def test_loads_only_enabled_commands(command_service: CommandService) -> None:
    ids = {c.id for c in command_service.list_commands()}
    assert ids == {"get_system_board", "get_uptime"}


def test_filters_by_category(command_service: CommandService) -> None:
    assert len(command_service.list_commands(category="sistema")) == 2


def test_list_categories(command_service: CommandService) -> None:
    assert command_service.list_categories() == ["sistema"]


def test_get_by_id_returns_command(command_service: CommandService) -> None:
    command = command_service.get_by_id("get_uptime")
    assert command.command == "uptime"


def test_get_by_id_rejects_unregistered_command(command_service: CommandService) -> None:
    with pytest.raises(CommandNotAllowedError):
        command_service.get_by_id("rm_rf")


def test_get_by_id_rejects_disabled_command(command_service: CommandService) -> None:
    with pytest.raises(CommandNotAllowedError):
        command_service.get_by_id("disabled_command")


def test_missing_file_returns_no_commands(tmp_path) -> None:
    service = CommandService(commands_file=tmp_path / "missing.yaml")
    assert service.list_commands() == []
