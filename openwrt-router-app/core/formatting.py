from __future__ import annotations

from datetime import datetime

_MONTHS_ES = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]


def format_datetime(value: datetime | str | None) -> str:
    """Formats a stored timestamp as a clear, human-readable date and time.

    Storage keeps the real timestamp (datetime column / ISO string in JSON);
    this only controls how it's *displayed*, e.g. "16 jul 2026, 12:54:33".
    """
    if value is None:
        return "-"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return f"{value.day} {_MONTHS_ES[value.month - 1]} {value.year}, {value:%H:%M:%S}"
