from __future__ import annotations

import pytest

from discovery.enums import AddressScope, CollectorType, ObservationType
from discovery.models import RawDiscoveryObservation
from discovery.normalization.normalizer import normalize_observation
from discovery.normalization.validators import (
    normalize_hostname,
    normalize_ipv4,
    normalize_ipv6,
    normalize_mac,
    normalize_thread_ext_address,
    normalize_timestamp,
)


def test_normalize_mac_accepts_colon_form() -> None:
    assert normalize_mac("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"


def test_normalize_mac_accepts_hyphen_and_bare_forms() -> None:
    assert normalize_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"
    assert normalize_mac("aabbccddeeff") == "aa:bb:cc:dd:ee:ff"


def test_normalize_mac_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_mac("not-a-mac")


def test_normalize_ipv4_valid_and_invalid() -> None:
    assert normalize_ipv4("192.168.1.10") == "192.168.1.10"
    with pytest.raises(ValueError):
        normalize_ipv4("999.999.999.999")


def test_normalize_ipv6_global() -> None:
    # 2001:db8::/32 is IANA's reserved documentation range (RFC 3849) and is
    # itself flagged `is_private` by Python's ipaddress module, so it can't
    # be used here to exercise the GLOBAL branch — use a real global unicast
    # address instead.
    address, scope = normalize_ipv6("2001:4860:4860::8888")
    assert address == "2001:4860:4860::8888"
    assert scope == AddressScope.GLOBAL


def test_normalize_ipv6_unique_local() -> None:
    _, scope = normalize_ipv6("fd00:1daf::60")
    assert scope == AddressScope.UNIQUE_LOCAL


def test_normalize_ipv6_link_local() -> None:
    _, scope = normalize_ipv6("fe80::1")
    assert scope == AddressScope.LINK_LOCAL


def test_normalize_ipv6_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_ipv6("not-an-ipv6")


def test_normalize_hostname_lowercases_and_strips_trailing_dot() -> None:
    assert normalize_hostname("ESP32-C6-01.") == "esp32-c6-01"


def test_normalize_hostname_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_hostname("not a hostname!")


def test_normalize_thread_ext_address_canonicalizes() -> None:
    assert normalize_thread_ext_address("00:11:22:33:44:55:66:77") == "00:11:22:33:44:55:66:77"
    assert normalize_thread_ext_address("0011223344556677") == "00:11:22:33:44:55:66:77"


def test_normalize_thread_ext_address_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        normalize_thread_ext_address("001122")


def test_normalize_timestamp_naive_gets_local_tz() -> None:
    result = normalize_timestamp("2026-07-29T18:00:00")
    assert result.tzinfo is not None


def test_normalize_observation_extracts_all_identifiers() -> None:
    raw = RawDiscoveryObservation(
        collector_id="c1",
        collector_type=CollectorType.SIMULATED_ROUTER,
        observed_at="2026-07-29T18:00:00-05:00",
        observation_type=ObservationType.DHCP_LEASE,
        source="router-dhcp",
        raw_payload={
            "hostname": "esp32-c6-01",
            "mac": "AA:BB:CC:DD:EE:FF",
            "ipv4": "192.168.1.50",
            "ipv6": ["fd00:1daf::50"],
            "device_type_hint": "ESP32_C6",
            "manufacturer_hint": "Espressif",
        },
    )
    normalized = normalize_observation(raw)
    assert normalized.hostname == "esp32-c6-01"
    assert normalized.manufacturer_hint == "Espressif"
    identifier_types = {i.identifier_type for i in normalized.identifiers}
    assert {"HOSTNAME", "MAC", "IPV4", "IPV6"} <= identifier_types
    assert len(normalized.addresses) == 2
    assert not normalized.normalization_errors


def test_normalize_observation_collects_errors_without_raising() -> None:
    raw = RawDiscoveryObservation(
        collector_id="c1",
        collector_type=CollectorType.SIMULATED_ROUTER,
        observed_at="2026-07-29T18:00:00-05:00",
        observation_type=ObservationType.DHCP_LEASE,
        source="router-dhcp",
        raw_payload={"hostname": "good-host", "mac": "not-a-mac", "ipv4": "999.999.999.999"},
    )
    normalized = normalize_observation(raw)
    # The valid hostname still comes through even though mac/ipv4 failed.
    assert normalized.hostname == "good-host"
    assert len(normalized.normalization_errors) == 2
