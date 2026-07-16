from __future__ import annotations

from datetime import datetime

from core.formatting import format_datetime


def test_formats_datetime_object() -> None:
    assert format_datetime(datetime(2026, 7, 16, 12, 54, 33, 930426)) == "16 jul 2026, 12:54:33"


def test_formats_iso_string() -> None:
    assert format_datetime("2026-07-16T12:54:33.930426-05:00") == "16 jul 2026, 12:54:33"


def test_none_returns_placeholder() -> None:
    assert format_datetime(None) == "-"


def test_unparseable_string_is_returned_unchanged() -> None:
    assert format_datetime("not-a-date") == "not-a-date"
