from __future__ import annotations

from core.exceptions import ParserError
from parsers.base import BaseParser


class DFParser(BaseParser):
    """Parses `df -h` output into one entry per filesystem."""

    def parse(self, raw_output: str) -> dict:
        lines = [line for line in raw_output.splitlines() if line.strip()]
        if len(lines) < 2:
            raise ParserError("No fue posible interpretar la salida de 'df': no hay filas de datos.")

        entries = []
        for line in lines[1:]:
            tokens = line.split()
            if len(tokens) < 6:
                continue
            filesystem, size, used, available, use_percent, *mountpoint_parts = tokens
            entries.append(
                {
                    "filesystem": filesystem,
                    "size": size,
                    "used": used,
                    "available": available,
                    "use_percent": use_percent.rstrip("%"),
                    "mountpoint": " ".join(mountpoint_parts),
                }
            )

        if not entries:
            raise ParserError("No fue posible interpretar ninguna fila de 'df'.")

        return {"filesystems": entries}
