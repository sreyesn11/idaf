from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from core.constants import COMMANDS_FILE
from core.exceptions import CommandConfigurationError, CommandNotAllowedError
from models.command import CommandDefinition


class CommandService:
    """Loads config/commands.yaml and is the only gateway to a valid, enabled command."""

    def __init__(self, commands_file: Path = COMMANDS_FILE) -> None:
        self._commands_file = commands_file
        self._commands: list[CommandDefinition] = []
        self.reload()

    def reload(self) -> None:
        self._commands = self._load_commands(self._commands_file)

    @staticmethod
    def _load_commands(commands_file: Path) -> list[CommandDefinition]:
        if not commands_file.exists():
            raise CommandConfigurationError(f"No se encontró el archivo de comandos: {commands_file}")

        with commands_file.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        entries = raw.get("commands") or []

        commands: list[CommandDefinition] = []
        seen_ids: set[str] = set()
        duplicate_ids: set[str] = set()
        for index, entry in enumerate(entries):
            try:
                command = CommandDefinition.model_validate(entry)
            except ValidationError as exc:
                identifier = entry.get("id", f"índice {index}") if isinstance(entry, dict) else f"índice {index}"
                raise CommandConfigurationError(
                    f"Comando inválido ('{identifier}') en {commands_file.name}: {exc}"
                ) from exc

            if command.id in seen_ids:
                duplicate_ids.add(command.id)
            seen_ids.add(command.id)
            commands.append(command)

        if duplicate_ids:
            raise CommandConfigurationError(
                f"IDs de comando duplicados en {commands_file.name}: {', '.join(sorted(duplicate_ids))}"
            )

        enabled_commands = [c for c in commands if c.enabled]
        if not enabled_commands:
            raise CommandConfigurationError(f"No hay comandos habilitados (enabled: true) en {commands_file.name}.")

        return enabled_commands

    def list_commands(self, category: str | None = None) -> list[CommandDefinition]:
        if category is None:
            return list(self._commands)
        return [c for c in self._commands if c.category == category]

    def list_categories(self) -> list[str]:
        return sorted({c.category for c in self._commands})

    def get_by_id(self, command_id: str) -> CommandDefinition:
        for command in self._commands:
            if command.id == command_id:
                return command
        raise CommandNotAllowedError(f"El comando '{command_id}' no está autorizado.")
