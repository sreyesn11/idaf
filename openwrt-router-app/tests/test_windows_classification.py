from __future__ import annotations

from discovery.collectors.windows_classification import ClassificationEvidence, classify
from discovery.enums import DeviceType


def test_openwrt_router_classified_from_dropbear_and_ports() -> None:
    evidence = ClassificationEvidence(
        ptr_hostname="OpenWrt.lan",
        ssh_banner="SSH-2.0-dropbear",
        open_ports={22, 80, 443},
    )

    result = classify(evidence)

    assert result.device_type == DeviceType.OPENWRT_ROUTER
    assert result.confidence >= 0.8
    assert len(result.evidence_notes) >= 2


def test_morse_micro_gateway_classified_when_branding_visible() -> None:
    evidence = ClassificationEvidence(
        ptr_hostname="ekh01-de87.lan",
        ssh_banner="SSH-2.0-dropbear",
        open_ports={22, 80, 443},
        http_body_snippet="Welcome to the Morse Micro HaLow gateway",
    )

    result = classify(evidence)

    assert result.device_type == DeviceType.IOT_GATEWAY
    assert result.manufacturer == "Morse Micro"
    assert result.confidence >= 0.8


def test_morse_micro_gateway_classified_with_lower_confidence_when_brand_unconfirmed() -> None:
    # Real-world case (validated against the actual lab devices): the router
    # and the Morse Micro gateway share an identical Dropbear + 22/80/443
    # signature, and `curl.exe -I` never returns a page body — so the only
    # available discriminator is a PTR hostname that isn't the primary
    # router's. Manufacturer can't be confirmed from headers alone.
    evidence = ClassificationEvidence(
        ptr_hostname="ekh01-de87.lan",
        ssh_banner="SSH-2.0-dropbear",
        open_ports={22, 80, 443},
    )

    result = classify(evidence)

    assert result.device_type == DeviceType.IOT_GATEWAY
    assert result.manufacturer is None
    assert result.confidence < 0.8
    assert any("manual" in note.lower() for note in result.evidence_notes)


def test_beagleplay_classified_from_nginx_and_openssh_debian() -> None:
    evidence = ClassificationEvidence(
        ptr_hostname="BeaglePlay.lan",
        ssh_banner="SSH-2.0-OpenSSH_8.4p1 Debian-5+deb11u2",
        http_headers={"server": "nginx/1.18.0"},
        open_ports={22, 80},
    )

    result = classify(evidence)

    assert result.device_type == DeviceType.BEAGLEPLAY
    assert result.confidence >= 0.8


def test_beagleplay_not_classified_if_443_is_open() -> None:
    evidence = ClassificationEvidence(
        ssh_banner="SSH-2.0-OpenSSH_8.4p1 Debian-5+deb11u2",
        http_headers={"server": "nginx/1.18.0"},
        open_ports={22, 80, 443},
    )

    result = classify(evidence)

    assert result.device_type != DeviceType.BEAGLEPLAY


def test_single_open_port_never_classifies_a_device() -> None:
    evidence = ClassificationEvidence(open_ports={22})

    result = classify(evidence)

    assert result.device_type == DeviceType.UNKNOWN
    assert result.confidence < 0.5


def test_no_evidence_at_all_is_unknown_with_low_confidence() -> None:
    result = classify(ClassificationEvidence())

    assert result.device_type == DeviceType.UNKNOWN
    assert result.manufacturer is None
    assert result.confidence < 0.5
    assert result.evidence_notes
