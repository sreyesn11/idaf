from __future__ import annotations

from parsers.base import BaseParser


class LinesParser(BaseParser):
    def parse(self, raw_output: str) -> dict:
        lines = [line for line in raw_output.splitlines() if line.strip() != ""]
        return {"lines": lines}
