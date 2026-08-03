from __future__ import annotations

from dataclasses import dataclass, field

from discovery.enums import DeviceType

_OPENWRT_PORTS = {22, 80, 443}


@dataclass
class ClassificationEvidence:
    ptr_hostname: str | None = None
    ssh_banner: str | None = None
    http_headers: dict[str, str] = field(default_factory=dict)
    http_body_snippet: str | None = None
    luci_reachable: bool | None = None
    open_ports: set[int] = field(default_factory=set)


@dataclass
class ClassificationResult:
    device_type: DeviceType
    manufacturer: str | None
    confidence: float
    evidence_notes: list[str]


def classify(evidence: ClassificationEvidence) -> ClassificationResult:
    """Evidence-based, explainable classification (spec section 8).

    Never decides from a single signal — every branch below requires at
    least two independent pieces of evidence to agree before committing to
    a specific device type; a lone open port is never enough.

    Validated against the real lab devices (spec section 3): the router and
    the Morse Micro gateway share an identical Dropbear + 22/80/443 HTTP
    header signature — `curl.exe -I` alone cannot tell them apart, since
    neither sends a distinguishing `Server` header and the allowed
    enrichment commands never fetch a page body. The one signal that DOES
    reliably differ between them is the PTR hostname (`OpenWrt.lan` vs.
    `ekh01-de87.lan`), so that's the secondary discriminator within the
    OpenWrt family — matched generically ("does the PTR mention openwrt"),
    never against the literal instance-specific hostname.
    """
    ssh_banner = (evidence.ssh_banner or "").lower()
    server_header = (evidence.http_headers.get("server") or "").lower()
    body = (evidence.http_body_snippet or "").lower()
    ptr = (evidence.ptr_hostname or "").lower()
    combined_text = f"{server_header} {body} {ptr}"

    has_dropbear = "dropbear" in ssh_banner
    has_luci = bool(evidence.luci_reachable) or "luci" in combined_text
    has_openwrt_ports = _OPENWRT_PORTS.issubset(evidence.open_ports)
    is_openwrt_family = has_openwrt_ports and (has_dropbear or has_luci)

    if is_openwrt_family:
        looks_like_primary_router = not ptr or "openwrt" in ptr
        base_notes = [
            "Puertos 22/80/443 abiertos (perfil OpenWrt)",
            "Banner Dropbear detectado" if has_dropbear else "Ruta LuCI alcanzable",
        ]
        if looks_like_primary_router:
            return ClassificationResult(DeviceType.OPENWRT_ROUTER, "OpenWrt", 0.9, base_notes)

        mentions_morse = "morse micro" in combined_text or "morse" in ptr
        manufacturer = "Morse Micro" if mentions_morse else None
        notes = [*base_notes, f"PTR '{evidence.ptr_hostname}' distinto del router principal"]
        if mentions_morse:
            notes.append("Marca 'Morse Micro' encontrada en evidencia disponible")
            return ClassificationResult(DeviceType.IOT_GATEWAY, manufacturer, 0.9, notes)
        notes.append("Fabricante no confirmado por la evidencia no invasiva disponible; requiere confirmación manual")
        return ClassificationResult(DeviceType.IOT_GATEWAY, manufacturer, 0.7, notes)

    has_openssh_debian = "openssh" in ssh_banner and "debian" in ssh_banner
    has_nginx = "nginx" in server_header
    port_443_closed = 443 not in evidence.open_ports
    has_22_and_80 = {22, 80}.issubset(evidence.open_ports)

    if has_openssh_debian and has_nginx and port_443_closed and has_22_and_80:
        notes = [
            "Banner OpenSSH sobre Debian",
            "Cabecera HTTP Server: nginx",
            "Puerto 443 cerrado; 22 y 80 abiertos",
        ]
        return ClassificationResult(DeviceType.BEAGLEPLAY, "Debian", 0.9, notes)

    notes = ["Evidencia insuficiente o ambigua para clasificar con confianza"]
    if evidence.open_ports:
        notes.append(f"Puertos observados: {sorted(evidence.open_ports)}")
    return ClassificationResult(DeviceType.UNKNOWN, None, 0.2, notes)
