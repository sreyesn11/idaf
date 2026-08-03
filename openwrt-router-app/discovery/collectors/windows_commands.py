from __future__ import annotations

import ipaddress
import json
import logging
import re
import subprocess
from typing import Callable

logger = logging.getLogger(__name__)

CommandRunner = Callable[..., subprocess.CompletedProcess]

_POWERSHELL_EXE = "powershell"
_SSH_BANNER_RE = re.compile(r"SSH-\d\.\d-[^\r\n]+")


def _run_powershell(script: str, timeout: float, runner: CommandRunner = subprocess.run) -> str | None:
    """Runs one PowerShell `-Command` script and returns stdout, or None on
    any failure. Never `shell=True`: `script` is the single -Command
    argument, not a shell string the OS re-parses."""
    args = [_POWERSHELL_EXE, "-NoProfile", "-NonInteractive", "-Command", script]
    try:
        result = runner(args, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Comando PowerShell agotó el tiempo o falló: %s", exc)
        return None
    if result.returncode != 0:
        logger.warning("Comando PowerShell terminó con código %s: %s", result.returncode, (result.stderr or "").strip())
        return None
    return result.stdout


def _parse_json(text: str | None) -> list[dict] | dict | None:
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Salida de PowerShell no es JSON válido")
        return None


def _as_list(data: list[dict] | dict | None) -> list[dict]:
    if data is None:
        return []
    return data if isinstance(data, list) else [data]


def validate_ip(value: str) -> str:
    """Raises ValueError if `value` isn't a real IPv4/IPv6 address.

    Every IP taken from a neighbor-cache row (untrusted, could be malformed)
    must pass through this before it's ever placed in a command argument.
    """
    return str(ipaddress.ip_address(value))


# Select-Object projection used for every Get-NetIPConfiguration call: the
# raw cmdlet output embeds a deeply nested CIM NetAdapter object (unrelated
# class metadata, easily 100x larger than needed and prone to truncating at
# -Depth 4); this pulls out exactly the fields the collector needs, verified
# against a real Windows 11 / PowerShell 7 machine.
_IP_CONFIG_SCRIPT_TEMPLATE = (
    "$c = Get-NetIPConfiguration {selector}; "
    "if ($c) {{ [PSCustomObject]@{{"
    "InterfaceAlias=$c.InterfaceAlias; InterfaceIndex=$c.InterfaceIndex; "
    "InterfaceDescription=$c.InterfaceDescription; "
    "IPv4Address=($c.IPv4Address | Select-Object -First 1 -ExpandProperty IPAddress); "
    "IPv6Address=($c.IPv6Address | Select-Object -ExpandProperty IPAddress); "
    "IPv4Gateway=($c.IPv4DefaultGateway | Select-Object -First 1 -ExpandProperty NextHop); "
    "DNSServer=($c.DNSServer | Select-Object -ExpandProperty ServerAddresses); "
    "MacAddress=(Get-NetAdapter -InterfaceIndex $c.InterfaceIndex).MacAddress; "
    "Status=(Get-NetAdapter -InterfaceIndex $c.InterfaceIndex).Status.ToString() "
    "}} | ConvertTo-Json -Depth 3 }}"
)


def get_net_ip_configuration(
    interface_index: int, timeout: float, runner: CommandRunner = subprocess.run
) -> dict | None:
    script = _IP_CONFIG_SCRIPT_TEMPLATE.format(selector=f"-InterfaceIndex {int(interface_index)}")
    items = _as_list(_parse_json(_run_powershell(script, timeout, runner)))
    return items[0] if items else None


def get_net_ip_configuration_by_alias(
    interface_alias: str, timeout: float, runner: CommandRunner = subprocess.run
) -> dict | None:
    """Used to locate an interface by alias when its index changed (spec section 2)."""
    escaped = interface_alias.replace("'", "''")
    script = _IP_CONFIG_SCRIPT_TEMPLATE.format(selector=f"-InterfaceAlias '{escaped}'")
    items = _as_list(_parse_json(_run_powershell(script, timeout, runner)))
    return items[0] if items else None


def get_net_neighbor(
    interface_index: int, address_family: str, timeout: float, runner: CommandRunner = subprocess.run
) -> list[dict]:
    if address_family not in ("IPv4", "IPv6"):
        raise ValueError(f"address_family inválido: {address_family}")
    script = (
        f"Get-NetNeighbor -InterfaceIndex {int(interface_index)} -AddressFamily {address_family} "
        "| Select-Object IPAddress, LinkLayerAddress, InterfaceIndex, "
        "@{N='State';E={$_.State.ToString()}} | ConvertTo-Json -Depth 3"
    )
    return _as_list(_parse_json(_run_powershell(script, timeout, runner)))


def resolve_dns_name(ip: str, timeout: float, runner: CommandRunner = subprocess.run) -> str | None:
    validated_ip = validate_ip(ip)
    script = f"Resolve-DnsName -Name '{validated_ip}' -ErrorAction SilentlyContinue | ConvertTo-Json -Depth 4"
    items = _as_list(_parse_json(_run_powershell(script, timeout, runner)))
    for item in items:
        name = item.get("NameHost") or item.get("Name")
        if name:
            return str(name).rstrip(".")
    return None


def test_net_connection(ip: str, port: int, timeout: float, runner: CommandRunner = subprocess.run) -> bool:
    validated_ip = validate_ip(ip)
    script = (
        f"Test-NetConnection -ComputerName '{validated_ip}' -Port {int(port)} "
        "-WarningAction SilentlyContinue | ConvertTo-Json -Depth 4"
    )
    items = _as_list(_parse_json(_run_powershell(script, timeout, runner)))
    return bool(items[0].get("TcpTestSucceeded")) if items else False


def curl_head(
    ip: str, port: int, use_tls: bool, timeout: float, runner: CommandRunner = subprocess.run, path: str = "/"
) -> dict | None:
    """HTTP(S) HEAD via curl.exe -I. Returns {"status_code", "headers"} or None."""
    validated_ip = validate_ip(ip)
    scheme = "https" if use_tls else "http"
    url = f"{scheme}://{validated_ip}:{int(port)}{path}"
    args = ["curl.exe", "-s", "-I", "-m", str(int(timeout))]
    if use_tls:
        args.append("-k")
    args.append(url)
    try:
        result = runner(args, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("curl.exe agotó el tiempo o falló: %s", exc)
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return _parse_http_head(result.stdout)


def _parse_http_head(raw: str) -> dict:
    status_code: int | None = None
    headers: dict[str, str] = {}
    for index, line in enumerate(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        if index == 0 and line.upper().startswith("HTTP/"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                status_code = int(parts[1])
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    return {"status_code": status_code, "headers": headers}


def ssh_keyscan(ip: str, timeout: float, runner: CommandRunner = subprocess.run) -> str | None:
    """Returns the remote SSH banner string (e.g. "SSH-2.0-dropbear") if
    observed, or None. Uses `ssh-keyscan -v`, which prints the banner line
    to stderr as a diagnostic; never opens an authenticated session."""
    validated_ip = validate_ip(ip)
    args = ["ssh-keyscan", "-v", "-T", str(int(timeout)), validated_ip]
    try:
        result = runner(args, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("ssh-keyscan agotó el tiempo o falló: %s", exc)
        return None
    combined = f"{result.stdout or ''}\n{result.stderr or ''}"
    match = _SSH_BANNER_RE.search(combined)
    return match.group(0).strip() if match else None
