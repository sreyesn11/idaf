from __future__ import annotations

import ipaddress
import logging

from discovery.enums import AddressFamily, AddressScope, DeviceType, IdentifierType
from discovery.models import (
    ExtractedAddress,
    ExtractedIdentifier,
    NormalizedObservation,
    RawDiscoveryObservation,
)
from discovery.normalization.validators import (
    dedupe_preserve_order,
    normalize_hostname,
    normalize_ipv4,
    normalize_ipv6,
    normalize_mac,
    normalize_mdns_name,
    normalize_thread_ext_address,
    normalize_timestamp,
)

logger = logging.getLogger(__name__)


def normalize_observation(raw: RawDiscoveryObservation) -> NormalizedObservation:
    """Turn one raw collector observation into a `NormalizedObservation`.

    Never raises on a single bad field: invalid values are recorded in
    `normalization_errors` and skipped, so one malformed identifier doesn't
    discard an otherwise-usable observation (spec section 9).
    """
    payload = raw.raw_payload
    errors: list[str] = []
    identifiers: list[ExtractedIdentifier] = []
    addresses: list[ExtractedAddress] = []

    observed_at = raw.observed_at
    try:
        observed_at = normalize_timestamp(raw.observed_at)
    except ValueError as exc:
        errors.append(str(exc))

    hostname: str | None = None
    if payload.get("hostname"):
        try:
            hostname = normalize_hostname(str(payload["hostname"]))
            identifiers.append(
                ExtractedIdentifier(
                    identifier_type=IdentifierType.HOSTNAME,
                    value=str(payload["hostname"]),
                    normalized_value=hostname,
                    confidence=1.0,
                )
            )
        except ValueError as exc:
            errors.append(str(exc))

    if payload.get("mdns_name"):
        try:
            mdns = normalize_mdns_name(str(payload["mdns_name"]))
            identifiers.append(
                ExtractedIdentifier(
                    identifier_type=IdentifierType.MDNS_NAME,
                    value=str(payload["mdns_name"]),
                    normalized_value=mdns,
                    confidence=1.0,
                )
            )
        except ValueError as exc:
            errors.append(str(exc))

    if payload.get("mac"):
        try:
            mac = normalize_mac(str(payload["mac"]))
            identifiers.append(
                ExtractedIdentifier(
                    identifier_type=IdentifierType.MAC,
                    value=str(payload["mac"]),
                    normalized_value=mac,
                    confidence=1.0,
                )
            )
        except ValueError as exc:
            errors.append(str(exc))

    if payload.get("agent_id"):
        identifiers.append(
            ExtractedIdentifier(
                identifier_type=IdentifierType.AGENT_ID,
                value=str(payload["agent_id"]),
                normalized_value=str(payload["agent_id"]).strip(),
                confidence=1.0,
            )
        )

    if payload.get("serial"):
        identifiers.append(
            ExtractedIdentifier(
                identifier_type=IdentifierType.SERIAL,
                value=str(payload["serial"]),
                normalized_value=str(payload["serial"]).strip().upper(),
                confidence=1.0,
            )
        )

    if payload.get("thread_ext_address"):
        try:
            thread_addr = normalize_thread_ext_address(str(payload["thread_ext_address"]))
            identifiers.append(
                ExtractedIdentifier(
                    identifier_type=IdentifierType.THREAD_EXT_ADDRESS,
                    value=str(payload["thread_ext_address"]),
                    normalized_value=thread_addr,
                    confidence=1.0,
                )
            )
        except ValueError as exc:
            errors.append(str(exc))

    if payload.get("rloc16"):
        identifiers.append(
            ExtractedIdentifier(
                identifier_type=IdentifierType.RLOC16,
                value=str(payload["rloc16"]),
                normalized_value=str(payload["rloc16"]).strip().lower(),
                confidence=0.6,
            )
        )

    if payload.get("ipv4"):
        try:
            ipv4 = normalize_ipv4(str(payload["ipv4"]))
            identifiers.append(
                ExtractedIdentifier(
                    identifier_type=IdentifierType.IPV4,
                    value=str(payload["ipv4"]),
                    normalized_value=ipv4,
                    confidence=0.5,
                )
            )
            addresses.append(
                ExtractedAddress(
                    address=ipv4,
                    address_family=AddressFamily.IPV4,
                    scope=_ipv4_scope(ipv4),
                )
            )
        except ValueError as exc:
            errors.append(str(exc))

    for raw_ipv6 in dedupe_preserve_order(_as_list(payload.get("ipv6"))):
        try:
            ipv6, scope = normalize_ipv6(raw_ipv6)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        identifiers.append(
            ExtractedIdentifier(
                identifier_type=IdentifierType.IPV6,
                value=raw_ipv6,
                normalized_value=ipv6,
                confidence=0.5,
            )
        )
        addresses.append(ExtractedAddress(address=ipv6, address_family=AddressFamily.IPV6, scope=scope))

    device_type_hint = None
    if payload.get("device_type_hint"):
        try:
            device_type_hint = DeviceType(str(payload["device_type_hint"]).upper())
        except ValueError:
            errors.append(f"device_type_hint desconocido: {payload['device_type_hint']!r}")

    return NormalizedObservation(
        observation_type=raw.observation_type,
        collector_id=raw.collector_id,
        collector_type=raw.collector_type,
        source=raw.source,
        observed_at=observed_at,
        device_type_hint=device_type_hint,
        hostname=hostname,
        manufacturer_hint=payload.get("manufacturer_hint"),
        parent_hostname=payload.get("parent_hostname"),
        identifiers=identifiers,
        addresses=addresses,
        normalization_errors=errors,
        raw_payload=payload,
    )


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _ipv4_scope(address: str) -> AddressScope:
    addr = ipaddress.IPv4Address(address)
    if addr.is_loopback:
        return AddressScope.LOOPBACK
    if addr.is_link_local:
        return AddressScope.LINK_LOCAL
    return AddressScope.GLOBAL
