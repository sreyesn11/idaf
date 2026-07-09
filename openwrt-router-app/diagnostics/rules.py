from __future__ import annotations

import re

from core.exceptions import RouterAppError
from diagnostics.enums import DiagnosticState
from diagnostics.models import DiagnosticCheckResult
from diagnostics.thresholds import (
    LoadThresholds,
    MemoryThresholds,
    SSHThresholds,
    StorageThresholds,
    UptimeThresholds,
)
from models.execution import ExecutionResult, ExecutionStatus

_COMPLETED_STATES = (ExecutionStatus.COMPLETED, ExecutionStatus.COMPLETED_WITH_WARNINGS)

# Used only to combine the uptime-seconds sub-rule and the load-ratio sub-rule
# into a single "uptime" check state (worst of the two wins).
_SEVERITY_RANK = {
    DiagnosticState.HEALTHY: 0,
    DiagnosticState.UNKNOWN: 1,
    DiagnosticState.WARNING: 2,
    DiagnosticState.DEGRADED: 3,
    DiagnosticState.CRITICAL: 4,
    DiagnosticState.UNREACHABLE: 5,
}

_DAY_RE = re.compile(r"(?P<days>\d+)\s*day")
_MIN_RE = re.compile(r"(?P<minutes>\d+)\s*min")
_HHMM_RE = re.compile(r"(?P<hours>\d+):(?P<minutes>\d+)$")


def _worst_state(states: list[DiagnosticState]) -> DiagnosticState:
    return max(states, key=lambda s: _SEVERITY_RANK[s])


def _is_usable(result: ExecutionResult | None) -> bool:
    return result is not None and result.status in _COMPLETED_STATES and result.parsed_data is not None


def _unknown(check_id: str, check_name: str, summary: str) -> DiagnosticCheckResult:
    return DiagnosticCheckResult(check_id=check_id, check_name=check_name, state=DiagnosticState.UNKNOWN, summary=summary)


def check_ssh(
    elapsed_ms: float | None,
    error: RouterAppError | None,
    thresholds: SSHThresholds,
) -> DiagnosticCheckResult:
    """Acceso SSH: alcanzabilidad y latencia de la conexión Paramiko."""
    if error is not None:
        return DiagnosticCheckResult(
            check_id="ssh",
            check_name="Acceso SSH",
            state=DiagnosticState.UNREACHABLE,
            summary=error.friendly_message,
            details={"detail": error.detail} if error.detail else {},
        )

    assert elapsed_ms is not None
    if elapsed_ms < thresholds.warning_latency_ms:
        state = DiagnosticState.HEALTHY
        summary = "La conexión SSH fue exitosa y la latencia es normal."
    elif elapsed_ms < thresholds.critical_latency_ms:
        state = DiagnosticState.WARNING
        summary = "La conexión SSH fue exitosa, pero la latencia es más alta de lo esperado."
    else:
        state = DiagnosticState.DEGRADED
        summary = "La conexión SSH fue exitosa, pero la latencia es muy alta."

    return DiagnosticCheckResult(
        check_id="ssh",
        check_name="Acceso SSH",
        state=state,
        summary=summary,
        value=round(elapsed_ms, 1),
        unit="ms",
    )


def check_identity(result: ExecutionResult | None) -> DiagnosticCheckResult:
    """Identidad del equipo: hostname, model, kernel y release desde `ubus call system board`."""
    if not _is_usable(result):
        return _unknown("identity", "Identidad del equipo", "No fue posible obtener la identidad del equipo.")

    data = result.parsed_data or {}
    required_fields = ["hostname", "model", "kernel", "release"]
    missing = [f for f in required_fields if data.get(f) in (None, "")]

    if not missing:
        state = DiagnosticState.HEALTHY
        summary = f"Identidad completa: {data.get('hostname')} ({data.get('model')})."
    else:
        state = DiagnosticState.WARNING
        summary = f"Identidad incompleta; faltan campos: {', '.join(missing)}."

    details = {field: data.get(field) for field in required_fields}
    return DiagnosticCheckResult(
        check_id="identity",
        check_name="Identidad del equipo",
        state=state,
        summary=summary,
        value=data.get("hostname"),
        details=details,
        evidence_execution_ids=[result.execution_id],
    )


def _parse_uptime_seconds(uptime_text: str) -> int | None:
    text = uptime_text.strip()
    total_seconds = 0
    matched = False

    day_match = _DAY_RE.search(text)
    if day_match:
        total_seconds += int(day_match.group("days")) * 86400
        matched = True
        text = text[day_match.end():].lstrip(", ")

    hhmm_match = _HHMM_RE.search(text)
    if hhmm_match:
        total_seconds += int(hhmm_match.group("hours")) * 3600 + int(hhmm_match.group("minutes")) * 60
        matched = True
    else:
        min_match = _MIN_RE.search(text)
        if min_match:
            total_seconds += int(min_match.group("minutes")) * 60
            matched = True

    return total_seconds if matched else None


def _extract_core_count(cores_result: ExecutionResult | None) -> int | None:
    if not _is_usable(cores_result):
        return None
    raw = (cores_result.parsed_data or {}).get("raw_text") or cores_result.stdout
    if not raw:
        return None
    match = re.search(r"\d+", raw)
    return int(match.group()) if match else None


def check_uptime(
    uptime_result: ExecutionResult | None,
    cores_result: ExecutionResult | None,
    uptime_thresholds: UptimeThresholds,
    load_thresholds: LoadThresholds,
) -> DiagnosticCheckResult:
    """Tiempo de actividad: combina el umbral de uptime en segundos (8.6) y la carga relativa por núcleo (8.5)."""
    if not _is_usable(uptime_result):
        return _unknown("uptime", "Tiempo de actividad", "No fue posible consultar el tiempo de actividad.")

    data = uptime_result.parsed_data or {}
    uptime_text = data.get("uptime")
    load_1m = data.get("load_1m")
    uptime_seconds = _parse_uptime_seconds(uptime_text) if uptime_text else None
    cores = _extract_core_count(cores_result)

    states: list[DiagnosticState] = []
    details: dict = {"uptime_text": uptime_text, "uptime_seconds": uptime_seconds, "cores": cores, "load_1m": load_1m}

    if uptime_seconds is None:
        states.append(DiagnosticState.UNKNOWN)
    elif uptime_seconds >= uptime_thresholds.warning_seconds:
        states.append(DiagnosticState.HEALTHY)
    else:
        states.append(DiagnosticState.WARNING)

    load_ratio = None
    if load_1m is not None and cores:
        load_ratio = load_1m / cores
        details["load_ratio"] = round(load_ratio, 2)
        if load_ratio < load_thresholds.warning_ratio_per_core:
            states.append(DiagnosticState.HEALTHY)
        elif load_ratio <= load_thresholds.critical_ratio_per_core:
            states.append(DiagnosticState.WARNING)
        else:
            states.append(DiagnosticState.CRITICAL)
    else:
        states.append(DiagnosticState.UNKNOWN)

    state = _worst_state(states)

    if uptime_seconds is not None and uptime_seconds < uptime_thresholds.warning_seconds:
        summary = "El router fue reiniciado recientemente."
    elif load_ratio is not None and load_ratio > load_thresholds.warning_ratio_per_core:
        summary = f"La carga del sistema es alta (ratio por núcleo: {load_ratio:.2f})."
    elif state == DiagnosticState.UNKNOWN:
        summary = "No fue posible calcular por completo el uptime o la carga del sistema."
    else:
        summary = "El tiempo de actividad y la carga del sistema son normales."

    evidence_ids = [uptime_result.execution_id]
    if cores_result is not None:
        evidence_ids.append(cores_result.execution_id)

    return DiagnosticCheckResult(
        check_id="uptime",
        check_name="Tiempo de actividad",
        state=state,
        summary=summary,
        value=uptime_seconds,
        unit="s",
        details=details,
        evidence_execution_ids=evidence_ids,
    )


def check_memory(result: ExecutionResult | None, thresholds: MemoryThresholds) -> DiagnosticCheckResult:
    """Memoria: porcentaje de uso a partir de `free` (used / total * 100)."""
    if not _is_usable(result):
        return _unknown("memory", "Memoria", "No fue posible consultar el uso de memoria.")

    data = result.parsed_data or {}
    total = data.get("total")
    used = data.get("used")
    if not isinstance(total, (int, float)) or not total or not isinstance(used, (int, float)):
        return _unknown("memory", "Memoria", "No fue posible calcular el porcentaje de uso de memoria.")

    percent = used / total * 100
    if percent < thresholds.warning_percent:
        state = DiagnosticState.HEALTHY
    elif percent < thresholds.critical_percent:
        state = DiagnosticState.WARNING
    else:
        state = DiagnosticState.CRITICAL

    details = {"total": total, "used": used, "available": data.get("available"), "percent": round(percent, 1)}
    return DiagnosticCheckResult(
        check_id="memory",
        check_name="Memoria",
        state=state,
        summary=f"Uso de memoria: {percent:.1f}%.",
        value=round(percent, 1),
        unit="%",
        details=details,
        evidence_execution_ids=[result.execution_id],
    )


def check_storage(result: ExecutionResult | None, thresholds: StorageThresholds) -> DiagnosticCheckResult:
    """Almacenamiento: porcentaje de uso del filesystem raíz (o el principal disponible) desde `df -h`."""
    if not _is_usable(result):
        return _unknown("storage", "Almacenamiento", "No fue posible consultar el uso de almacenamiento.")

    filesystems = (result.parsed_data or {}).get("filesystems") or []
    if not filesystems:
        return _unknown("storage", "Almacenamiento", "No se encontraron filesystems en la salida de 'df'.")

    target = next((fs for fs in filesystems if fs.get("mountpoint") == "/"), filesystems[0])
    try:
        percent = float(str(target.get("use_percent", "")).rstrip("%"))
    except (TypeError, ValueError):
        return _unknown("storage", "Almacenamiento", "No fue posible interpretar el porcentaje de uso reportado.")

    if percent < thresholds.warning_percent:
        state = DiagnosticState.HEALTHY
    elif percent < thresholds.critical_percent:
        state = DiagnosticState.WARNING
    else:
        state = DiagnosticState.CRITICAL

    details = {
        "mountpoint": target.get("mountpoint"),
        "size": target.get("size"),
        "used": target.get("used"),
        "available": target.get("available"),
        "percent": percent,
    }
    return DiagnosticCheckResult(
        check_id="storage",
        check_name="Almacenamiento",
        state=state,
        summary=f"Uso de almacenamiento en {target.get('mountpoint')}: {percent:.1f}%.",
        value=percent,
        unit="%",
        details=details,
        evidence_execution_ids=[result.execution_id],
    )


def check_lan(result: ExecutionResult | None) -> DiagnosticCheckResult:
    """LAN: estado `up` y presencia de dirección IPv4 desde `ubus call network.interface.lan status`."""
    if not _is_usable(result):
        return _unknown("lan", "LAN", "No fue posible consultar el estado de la interfaz LAN.")

    data = result.parsed_data or {}
    up = bool(data.get("up"))
    addresses = data.get("ipv4-address") or []
    has_ip = len(addresses) > 0

    if up and has_ip:
        state = DiagnosticState.HEALTHY
        summary = "La interfaz LAN está activa y tiene dirección IPv4."
    elif up:
        state = DiagnosticState.WARNING
        summary = "La interfaz LAN está activa pero no tiene dirección IPv4."
    else:
        state = DiagnosticState.DEGRADED
        summary = "La interfaz LAN no está activa."

    details = {
        "up": up,
        "l3_device": data.get("l3_device"),
        "ipv4_addresses": [a.get("address") for a in addresses if isinstance(a, dict)],
    }
    return DiagnosticCheckResult(
        check_id="lan",
        check_name="LAN",
        state=state,
        summary=summary,
        value=up,
        details=details,
        evidence_execution_ids=[result.execution_id],
    )


def check_wan(result: ExecutionResult | None, required: bool) -> DiagnosticCheckResult:
    """WAN: estado `up` desde `ubus call network.interface.wan status`; no es obligatoria salvo configuración."""
    if not _is_usable(result):
        return _unknown("wan", "WAN", "No fue posible consultar el estado de la interfaz WAN.")

    data = result.parsed_data or {}
    up = bool(data.get("up"))

    if up:
        state = DiagnosticState.HEALTHY
        summary = "La interfaz WAN está activa."
    elif required:
        state = DiagnosticState.DEGRADED
        summary = "La interfaz WAN no está activa y es obligatoria en esta configuración."
    else:
        state = DiagnosticState.WARNING
        summary = "El router está operativo, pero la WAN no tiene conectividad."

    details = {"up": up, "required": required}
    return DiagnosticCheckResult(
        check_id="wan",
        check_name="WAN",
        state=state,
        summary=summary,
        value=up,
        details=details,
        evidence_execution_ids=[result.execution_id],
    )


def check_ipv6(result: ExecutionResult | None, required: bool) -> DiagnosticCheckResult:
    """IPv6: presencia de direcciones globales/ULA vs. solo link-local, desde `ip -6 addr show`."""
    if not _is_usable(result):
        return _unknown("ipv6", "IPv6", "No fue posible consultar las direcciones IPv6.")

    raw_text = (result.parsed_data or {}).get("raw_text", "")
    matches = re.findall(r"inet6\s+([0-9a-fA-F:]+)/\d+\s+scope\s+(\S+)", raw_text)
    # "scope host" is the loopback (::1) and is always present regardless of
    # network configuration; it must not count as a "global/ULA" address.
    non_loopback = [(addr, scope) for addr, scope in matches if scope != "host"]
    global_addresses = [addr for addr, scope in non_loopback if scope == "global"]

    if global_addresses:
        state = DiagnosticState.HEALTHY
        summary = "Existen direcciones IPv6 globales o ULA."
    elif non_loopback:
        state = DiagnosticState.WARNING
        summary = "Solo existen direcciones IPv6 link-local."
    else:
        state = DiagnosticState.WARNING
        summary = "No se detectaron direcciones IPv6 configuradas."

    details = {
        "addresses": [addr for addr, _ in non_loopback],
        "global_count": len(global_addresses),
        "required": required,
    }
    return DiagnosticCheckResult(
        check_id="ipv6",
        check_name="IPv6",
        state=state,
        summary=summary,
        details=details,
        evidence_execution_ids=[result.execution_id],
    )


def check_wifi(result: ExecutionResult | None, required: bool) -> DiagnosticCheckResult:
    """Wi-Fi: radios activas/deshabilitadas desde `ubus call network.wireless status`."""
    if result is None or result.status in (ExecutionStatus.FAILED, ExecutionStatus.TIMEOUT) or not result.parsed_data:
        return _unknown("wifi", "Wi-Fi", "El comando de estado inalámbrico no está disponible.")

    radios = result.parsed_data
    if not isinstance(radios, dict) or not radios:
        return _unknown("wifi", "Wi-Fi", "No se detectaron radios inalámbricas.")

    radio_entries = {k: v for k, v in radios.items() if isinstance(v, dict)}
    any_up = any(bool(radio.get("up")) for radio in radio_entries.values())
    any_disabled = any(bool(radio.get("disabled")) for radio in radio_entries.values())

    if any_up:
        state = DiagnosticState.HEALTHY
        summary = "Al menos una radio inalámbrica está activa."
    elif any_disabled:
        state = DiagnosticState.WARNING
        summary = "Las radios inalámbricas están presentes pero deshabilitadas."
    else:
        state = DiagnosticState.WARNING
        summary = "No hay radios inalámbricas activas."

    details = {"radios": list(radio_entries.keys()), "any_up": any_up, "required": required}
    return DiagnosticCheckResult(
        check_id="wifi",
        check_name="Wi-Fi",
        state=state,
        summary=summary,
        details=details,
        evidence_execution_ids=[result.execution_id],
    )
