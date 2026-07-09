from __future__ import annotations

import json

from core.exceptions import ParserError
from parsers.base import BaseParser


class JSONParser(BaseParser):
    """For ubus-style commands, which print a single JSON object."""

    def parse(self, raw_output: str) -> dict:
        text = raw_output.strip()
        if not text:
            raise ParserError("La salida JSON está vacía.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ParserError(f"La salida no es JSON válido: {exc}") from exc
        if isinstance(data, dict):
            return data
        return {"value": data}
