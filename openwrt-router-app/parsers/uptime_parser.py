from __future__ import annotations

import re

from core.exceptions import ParserError
from parsers.base import BaseParser


class UptimeParser(BaseParser):
    """Parses the output of `uptime`. Tolerant of BusyBox variants that omit the users field."""

    _PATTERN = re.compile(
        r"^\s*(?P<time>\d{1,2}:\d{2}:\d{2})\s+up\s+(?P<uptime>.+?),\s*"
        r"(?:(?P<users>\d+)\s+users?,\s*)?"
        r"load average:\s*(?P<load1>[\d.]+),\s*(?P<load5>[\d.]+),\s*(?P<load15>[\d.]+)"
    )

    def parse(self, raw_output: str) -> dict:
        text = raw_output.strip()
        match = self._PATTERN.search(text)
        if not match:
            raise ParserError("No fue posible interpretar la salida de 'uptime'.")

        users = match.group("users")
        return {
            "time": match.group("time"),
            "uptime": match.group("uptime").strip(),
            "users": int(users) if users is not None else None,
            "load_1m": float(match.group("load1")),
            "load_5m": float(match.group("load5")),
            "load_15m": float(match.group("load15")),
        }
