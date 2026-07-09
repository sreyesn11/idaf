from __future__ import annotations


class BaseParser:
    def parse(self, raw_output: str) -> dict:
        raise NotImplementedError
