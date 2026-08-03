from __future__ import annotations

import json
import subprocess

import pytest

from core.exceptions import DiscoveryFixtureError
from discovery.collectors.windows_neighbor import WindowsNeighborCollector
from discovery.config import DiscoveryConfig
from discovery.enums import ObservationType

_INTERFACE = {
    "InterfaceAlias": "Ethernet",
    "InterfaceIndex": 23,
    "InterfaceDescription": "Realtek PCIe GbE Family Controller",
    "IPv4Address": "192.168.1.102",
    "IPv6Address": "fd49:98b1:e79:7f7e:9900:750:eaf3:336",
    "IPv4Gateway": "192.168.1.1",
    "DNSServer": "192.168.1.1",
    "MacAddress": "08-97-98-DC-90-59",
    "Status": "Up",
}

# Mirrors a real `Get-NetNeighbor -AddressFamily IPv4` capture: the three
# known lab devices plus realistic noise (broadcast, multicast, zero-MAC
# unresolved entries) that must all be filtered out.
_NEIGHBORS_IPV4 = [
    {"IPAddress": "255.255.255.255", "LinkLayerAddress": "FF-FF-FF-FF-FF-FF", "InterfaceIndex": 23, "State": "Permanent"},
    {"IPAddress": "239.255.255.250", "LinkLayerAddress": "01-00-5E-7F-FF-FA", "InterfaceIndex": 23, "State": "Permanent"},
    {"IPAddress": "192.168.1.255", "LinkLayerAddress": "FF-FF-FF-FF-FF-FF", "InterfaceIndex": 23, "State": "Permanent"},
    {"IPAddress": "192.168.1.227", "LinkLayerAddress": "34-08-E1-85-4B-C8", "InterfaceIndex": 23, "State": "Stale"},
    {"IPAddress": "192.168.1.217", "LinkLayerAddress": "00-00-00-00-00-00", "InterfaceIndex": 23, "State": "Unreachable"},
    {"IPAddress": "192.168.1.111", "LinkLayerAddress": "88-A2-9E-1C-DE-87", "InterfaceIndex": 23, "State": "Probe"},
    {"IPAddress": "192.168.1.1", "LinkLayerAddress": "60-38-E0-12-9D-41", "InterfaceIndex": 23, "State": "Reachable"},
    {"IPAddress": "192.168.1.102", "LinkLayerAddress": "08-97-98-DC-90-59", "InterfaceIndex": 23, "State": "Permanent"},
]

_NEIGHBORS_IPV6 = [
    {"IPAddress": "ff02::1:ff1c:de87", "LinkLayerAddress": "33-33-FF-1C-DE-87", "InterfaceIndex": 23, "State": "Permanent"},
    {"IPAddress": "fe80::8aa2:9eff:fe1c:de87", "LinkLayerAddress": "88-A2-9E-1C-DE-87", "InterfaceIndex": 23, "State": "Stale"},
]

_PTR = {
    "192.168.1.227": "BeaglePlay.lan",
    "192.168.1.111": "ekh01-de87.lan",
    "192.168.1.1": "OpenWrt.lan",
}

_ENRICHMENT = {
    "192.168.1.227": {
        "open_ports": {22, 80},
        "ssh_banner": "SSH-2.0-OpenSSH_8.4p1 Debian-5+deb11u2",
        "http_headers": {"server": "nginx/1.18.0"},
    },
    "192.168.1.111": {
        "open_ports": {22, 80, 443},
        "ssh_banner": "SSH-2.0-dropbear",
        "http_headers": {},
        "luci": True,
    },
    "192.168.1.1": {
        "open_ports": {22, 80, 443},
        "ssh_banner": "SSH-2.0-dropbear",
        "http_headers": {},
        "luci": True,
    },
}


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class FakeRunner:
    """Stands in for `subprocess.run`, dispatching on the command being invoked
    exactly as `discovery/collectors/windows_commands.py` builds it — no real
    process is ever spawned."""

    def __init__(self, interface=_INTERFACE, ipv4=_NEIGHBORS_IPV4, ipv6=_NEIGHBORS_IPV6, ptr=_PTR, enrichment=_ENRICHMENT):
        self.interface = interface
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.ptr = ptr
        self.enrichment = enrichment
        self.calls: list[list[str]] = []

    def __call__(self, args, capture_output=True, text=True, timeout=None):
        self.calls.append(args)
        if args[0] == "powershell":
            return self._powershell(args[-1])
        if args[0] == "ssh-keyscan":
            return self._ssh_keyscan(args[-1])
        if args[0] == "curl.exe":
            return self._curl(args[-1])
        raise AssertionError(f"unexpected command: {args}")

    def _powershell(self, script: str) -> subprocess.CompletedProcess:
        if "Get-NetIPConfiguration" in script:
            if self.interface is None:
                return _completed("")
            return _completed(json.dumps(self.interface))
        if "Get-NetNeighbor" in script:
            data = self.ipv4 if "IPv4" in script else self.ipv6
            return _completed(json.dumps(data))
        if "Resolve-DnsName" in script:
            ip = script.split("-Name '")[1].split("'")[0]
            hostname = self.ptr.get(ip)
            return _completed(json.dumps({"NameHost": hostname}) if hostname else "")
        if "Test-NetConnection" in script:
            ip = script.split("-ComputerName '")[1].split("'")[0]
            port = int(script.split("-Port ")[1].split(" ")[0])
            open_ports = self.enrichment.get(ip, {}).get("open_ports", set())
            return _completed(json.dumps({"TcpTestSucceeded": port in open_ports}))
        raise AssertionError(f"unexpected PowerShell script: {script}")

    def _ssh_keyscan(self, ip: str) -> subprocess.CompletedProcess:
        banner = self.enrichment.get(ip, {}).get("ssh_banner")
        if banner:
            return _completed("", stderr=f"# {ip}:22 {banner}\n")
        return _completed("")

    def _curl(self, url: str) -> subprocess.CompletedProcess:
        ip = url.split("://", 1)[1].split(":", 1)[0]
        info = self.enrichment.get(ip, {})
        if "/cgi-bin/luci/" in url:
            status = "200 OK" if info.get("luci") else "404 Not Found"
            return _completed(f"HTTP/1.1 {status}\r\n\r\n")
        headers = info.get("http_headers")
        if headers is None:
            return _completed("", returncode=7)
        lines = ["HTTP/1.1 200 OK"] + [f"{k.title()}: {v}" for k, v in headers.items()]
        return _completed("\r\n".join(lines) + "\r\n\r\n")


def _make_collector(runner: FakeRunner, allow_active_enrichment: bool = True) -> WindowsNeighborCollector:
    config = DiscoveryConfig(
        interface_alias="Ethernet",
        interface_index=23,
        allow_active_enrichment=allow_active_enrichment,
        command_timeout_seconds=5,
    )
    return WindowsNeighborCollector(config, run_command=runner)


def test_collect_produces_one_observation_per_known_device() -> None:
    runner = FakeRunner()
    collector = _make_collector(runner)

    observations = collector.collect()

    assert len(observations) == 3
    by_mac = {obs.raw_payload["mac"]: obs for obs in observations}
    assert set(by_mac.keys()) == {"34-08-E1-85-4B-C8", "88-A2-9E-1C-DE-87", "60-38-E0-12-9D-41"}


def test_morse_micro_dual_stack_is_a_single_observation() -> None:
    collector = _make_collector(FakeRunner())

    observations = collector.collect()

    morse = next(obs for obs in observations if obs.raw_payload["mac"] == "88-A2-9E-1C-DE-87")
    assert morse.raw_payload["ipv4"] == "192.168.1.111"
    assert morse.raw_payload["ipv6"] == ["fe80::8aa2:9eff:fe1c:de87"]
    assert morse.observation_type == ObservationType.IPV4_NEIGHBOR


def test_classification_hints_match_known_devices() -> None:
    collector = _make_collector(FakeRunner())

    observations = collector.collect()

    by_mac = {obs.raw_payload["mac"]: obs.raw_payload for obs in observations}
    assert by_mac["60-38-E0-12-9D-41"]["device_type_hint"] == "OPENWRT_ROUTER"
    assert by_mac["88-A2-9E-1C-DE-87"]["device_type_hint"] == "IOT_GATEWAY"
    assert by_mac["34-08-E1-85-4B-C8"]["device_type_hint"] == "BEAGLEPLAY"


def test_filters_broadcast_multicast_zero_mac_unreachable_and_self() -> None:
    collector = _make_collector(FakeRunner())

    observations = collector.collect()

    # 8 raw IPv4 rows - 5 noise rows (broadcast x2, multicast, zero-MAC
    # unreachable, self) = 3 kept; interface's own address must never
    # become a "discovered" device.
    macs = {obs.raw_payload["mac"] for obs in observations}
    assert "08-97-98-DC-90-59" not in macs
    assert "FF-FF-FF-FF-FF-FF" not in macs
    assert "01-00-5E-7F-FF-FA" not in macs
    assert collector.last_run_stats["filtered_entries"] == 5 + 1  # + the lone multicast IPv6 row


def test_hostname_resolved_for_each_device() -> None:
    collector = _make_collector(FakeRunner())

    observations = collector.collect()

    hostnames = {obs.raw_payload["mac"]: obs.raw_payload.get("hostname") for obs in observations}
    assert hostnames["60-38-E0-12-9D-41"] == "OpenWrt.lan"
    assert hostnames["88-A2-9E-1C-DE-87"] == "ekh01-de87.lan"
    assert hostnames["34-08-E1-85-4B-C8"] == "BeaglePlay.lan"


def test_no_enrichment_means_no_classification_evidence() -> None:
    collector = _make_collector(FakeRunner(), allow_active_enrichment=False)

    observations = collector.collect()

    for obs in observations:
        assert obs.raw_payload["device_type_hint"] == "UNKNOWN"
        assert obs.raw_payload["classification_confidence"] < 0.5


def test_last_run_stats_populated() -> None:
    collector = _make_collector(FakeRunner())

    collector.collect()

    stats = collector.last_run_stats
    assert stats is not None
    assert stats["interface"]["alias"] == "Ethernet"
    assert stats["interface"]["index"] == 23
    assert stats["raw_ipv4_neighbors"] == len(_NEIGHBORS_IPV4)
    assert stats["raw_ipv6_neighbors"] == len(_NEIGHBORS_IPV6)


def test_interface_alias_mismatch_raises_and_names_new_index() -> None:
    # Interface 23 no longer answers to "Ethernet"; the alias lookup finds
    # it moved to a different index (47) — the collector must refuse to
    # proceed silently and name the new index in the error.
    mismatched_interface = {**_INTERFACE, "InterfaceIndex": 23, "InterfaceAlias": "Wi-Fi"}

    class _AliasAwareRunner(FakeRunner):
        def _powershell(self, script: str) -> subprocess.CompletedProcess:
            if "Get-NetIPConfiguration" in script and "-InterfaceAlias" in script:
                return _completed(json.dumps({**_INTERFACE, "InterfaceIndex": 47}))
            return super()._powershell(script)

    collector = _make_collector(_AliasAwareRunner(interface=mismatched_interface))

    with pytest.raises(DiscoveryFixtureError, match="47"):
        collector.collect()


def test_interface_not_found_raises() -> None:
    runner = FakeRunner(interface=None)
    collector = _make_collector(runner)

    with pytest.raises(DiscoveryFixtureError):
        collector.collect()
