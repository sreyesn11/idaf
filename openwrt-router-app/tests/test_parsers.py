from __future__ import annotations

import pytest

from core.exceptions import ParserError
from parsers.df_parser import DFParser
from parsers.free_parser import FreeParser
from parsers.json_parser import JSONParser
from parsers.lines_parser import LinesParser
from parsers.text_parser import TextParser
from parsers.uptime_parser import UptimeParser


def test_json_parser_parses_object() -> None:
    result = JSONParser().parse('{"hostname": "OpenWrt", "model": "OpenWrt One"}')
    assert result == {"hostname": "OpenWrt", "model": "OpenWrt One"}


def test_json_parser_rejects_empty_output() -> None:
    with pytest.raises(ParserError):
        JSONParser().parse("")


def test_json_parser_rejects_invalid_json() -> None:
    with pytest.raises(ParserError):
        JSONParser().parse("{not valid json")


def test_text_parser_wraps_raw_output() -> None:
    assert TextParser().parse("hola mundo") == {"raw_text": "hola mundo"}


def test_lines_parser_splits_non_empty_lines() -> None:
    result = LinesParser().parse("linea 1\n\nlinea 2\n")
    assert result == {"lines": ["linea 1", "linea 2"]}


def test_uptime_parser_extracts_fields_with_users() -> None:
    raw = " 20:15:00 up 3 days,  2:31,  2 users,  load average: 0.10, 0.05, 0.02"
    result = UptimeParser().parse(raw)
    assert result["time"] == "20:15:00"
    assert result["users"] == 2
    assert result["load_1m"] == 0.10
    assert result["load_5m"] == 0.05
    assert result["load_15m"] == 0.02


def test_uptime_parser_without_users_field() -> None:
    raw = " 20:15:00 up 3 days, 2:31, load average: 0.10, 0.05, 0.02"
    result = UptimeParser().parse(raw)
    assert result["users"] is None
    assert result["load_1m"] == 0.10


def test_uptime_parser_raises_on_unrecognized_output() -> None:
    with pytest.raises(ParserError):
        UptimeParser().parse("salida completamente inesperada")


def test_free_parser_extracts_memory_fields() -> None:
    raw = (
        "             total       used       free     shared  buffers\n"
        "Mem:        128000      64000      64000          0     2000\n"
    )
    result = FreeParser().parse(raw)
    assert result["total"] == 128000
    assert result["used"] == 64000
    assert result["free"] == 64000


def test_free_parser_raises_without_mem_line() -> None:
    with pytest.raises(ParserError):
        FreeParser().parse("salida sin informacion de memoria")


def test_df_parser_extracts_filesystem_rows() -> None:
    raw = (
        "Filesystem                Size      Used Available Use% Mounted on\n"
        "/dev/root                12.7M     12.7M         0 100% /rom\n"
        "tmpfs                    59.9M    424.0K     59.5M   1% /tmp\n"
    )
    result = DFParser().parse(raw)
    assert len(result["filesystems"]) == 2
    first = result["filesystems"][0]
    assert first["filesystem"] == "/dev/root"
    assert first["mountpoint"] == "/rom"
    assert first["use_percent"] == "100"


def test_df_parser_raises_without_data_rows() -> None:
    with pytest.raises(ParserError):
        DFParser().parse("Filesystem Size Used Available Use% Mounted on\n")
