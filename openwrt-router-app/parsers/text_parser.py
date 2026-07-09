from __future__ import annotations

from parsers.base import BaseParser


class TextParser(BaseParser):
    def parse(self, raw_output: str) -> dict:
        return {"raw_text": raw_output}
