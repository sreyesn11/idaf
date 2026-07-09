from __future__ import annotations

from core.exceptions import ParserError
from parsers.base import BaseParser

_FIELD_ORDER = ["total", "used", "free", "shared", "buffers_cache", "available"]


class FreeParser(BaseParser):
    """Best-effort parser for `free`. Column names vary between BusyBox and procps,
    so values are mapped positionally from the 'Mem:' row instead of relying on headers.
    """

    def parse(self, raw_output: str) -> dict:
        mem_line = next(
            (line for line in raw_output.splitlines() if line.strip().lower().startswith("mem:")),
            None,
        )
        if mem_line is None:
            raise ParserError("No fue posible interpretar la salida de 'free': no se encontró la línea 'Mem:'.")

        tokens = mem_line.split()[1:]
        result: dict = {}
        for key, value in zip(_FIELD_ORDER, tokens):
            try:
                result[key] = int(value)
            except ValueError:
                result[key] = value
        return result
