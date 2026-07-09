from __future__ import annotations

from pathlib import Path

import yaml

from core.constants import COMMANDS_FILE
from core.exceptions import CommandNotAllowedError
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
            return []
        with commands_file.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        entries = raw.get("commands", [])
        commands = [CommandDefinition.model_validate(entry) for entry in entries]
        return [c for c in commands if c.enabled]

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
