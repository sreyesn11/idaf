from __future__ import annotations

import ipaddress
import re
from datetime import datetime

from discovery.enums import AddressScope

_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
_THREAD_EXT_ADDR_RE = re.compile(r"^[0-9a-f]{16}$")
_HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")


def normalize_mac(value: str) -> str:
    """Canonicalize a MAC address to lowercase colon-separated form.

    Accepts colon, hyphen, or bare-hex input (`AA:BB:...`, `aa-bb-...`,
    `aabbccddeeff`). Raises ValueError for anything else — never guesses.
    """
    cleaned = value.strip().lower().replace("-", ":")
    if ":" not in cleaned and len(cleaned) == 12:
        cleaned = ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))
    if not _MAC_RE.match(cleaned):
        raise ValueError(f"MAC inválida: {value!r}")
    return cleaned


def normalize_ipv4(value: str) -> str:
    try:
        return str(ipaddress.IPv4Address(value.strip()))
    except ValueError as exc:
        raise ValueError(f"IPv4 inválida: {value!r}") from exc


def normalize_ipv6(value: str) -> tuple[str, AddressScope]:
    try:
        addr = ipaddress.IPv6Address(value.strip())
    except ValueError as exc:
        raise ValueError(f"IPv6 inválida: {value!r}") from exc
    if addr.is_loopback:
        scope = AddressScope.LOOPBACK
    elif addr.is_link_local:
        scope = AddressScope.LINK_LOCAL
    elif addr.is_private:
        # Mainly fc00::/7 (Unique Local Addresses) — ipaddress has no
        # dedicated `is_unique_local`. A few reserved-but-not-ULA ranges
        # (e.g. the 2001:db8::/32 documentation prefix) are also flagged
        # `is_private`; real devices won't hand those out, so classifying
        # them as ULA here is an acceptable simplification.
        scope = AddressScope.UNIQUE_LOCAL
    else:
        scope = AddressScope.GLOBAL
    return str(addr.compressed), scope


def normalize_hostname(value: str) -> str:
    cleaned = value.strip().lower().rstrip(".")
    if not cleaned or not _HOSTNAME_RE.match(cleaned):
        raise ValueError(f"Hostname inválido: {value!r}")
    return cleaned


def normalize_mdns_name(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned.endswith(".local") and not cleaned.endswith(".local."):
        cleaned = f"{cleaned}.local"
    return normalize_hostname(cleaned)


def normalize_thread_ext_address(value: str) -> str:
    cleaned = value.strip().lower().replace(":", "").replace("-", "")
    if not _THREAD_EXT_ADDR_RE.match(cleaned):
        raise ValueError(f"Thread Extended Address inválida: {value!r}")
    return ":".join(cleaned[i : i + 2] for i in range(0, 16, 2))


def normalize_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip())
        except ValueError as exc:
            raise ValueError(f"Timestamp inválido: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
