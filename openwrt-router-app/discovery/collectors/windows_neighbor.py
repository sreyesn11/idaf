from __future__ import annotations

import ipaddress
import logging
import subprocess
from datetime import datetime

from core.exceptions import DiscoveryFixtureError
from discovery.collectors.windows_classification import ClassificationEvidence, classify
from discovery.collectors.windows_commands import (
    CommandRunner,
    curl_head,
    get_net_ip_configuration,
    get_net_ip_configuration_by_alias,
    get_net_neighbor,
    resolve_dns_name,
    ssh_keyscan,
    test_net_connection,
)
from discovery.config import DiscoveryConfig
from discovery.enums import CollectorType, ObservationType
from discovery.models import RawDiscoveryObservation

logger = logging.getLogger(__name__)

_BROADCAST_MAC = "FF-FF-FF-FF-FF-FF"
_ZERO_MAC = "00-00-00-00-00-00"
_IPV4_MULTICAST_NET = ipaddress.ip_network("224.0.0.0/4")
_IPV6_MULTICAST_NET = ipaddress.ip_network("ff00::/8")
_ACTIVE_STATES = {"Reachable", "Stale", "Probe", "Delay"}


class WindowsNeighborCollector:
    """Collects real IPv4/IPv6 neighbor-cache entries from one Windows
    Ethernet interface (spec doc 03) and turns them into the exact same
    `RawDiscoveryObservation` shape `SimulatedDiscoveryCollector` produces.

    Only ever reads the neighbor cache and optionally probes a handful of
    already-observed IPs (spec section 4) — never opens an SSH session,
    never modifies a router, never sweeps a subnet.
    """

    def __init__(
        self,
        config: DiscoveryConfig,
        run_command: CommandRunner = subprocess.run,
        clock: callable = lambda: datetime.now().astimezone(),
    ) -> None:
        self.collector_type = CollectorType.WINDOWS_NEIGHBOR
        self.last_run_stats: dict | None = None
        self._config = config
        self._run_command = run_command
        self._clock = clock

    def collect(self) -> list[RawDiscoveryObservation]:
        interface = self._validate_interface()
        interface_index = int(interface["InterfaceIndex"])

        ipv4_entries = get_net_neighbor(interface_index, "IPv4", self._config.command_timeout_seconds, self._run_command)
        ipv6_entries = get_net_neighbor(interface_index, "IPv6", self._config.command_timeout_seconds, self._run_command)

        own_addresses = {a for a in (interface.get("IPv4Address"), *_as_list(interface.get("IPv6Address"))) if a}

        filtered, filtered_out_count = self._filter(ipv4_entries + ipv6_entries, interface, own_addresses)
        candidates = self._group_by_mac(filtered)

        observed_at = self._clock()
        observations = [
            self._build_observation(candidate, interface_index, observed_at) for candidate in candidates
        ]

        self.last_run_stats = {
            "interface": {
                "alias": interface.get("InterfaceAlias"),
                "index": interface_index,
                "ipv4": interface.get("IPv4Address"),
                "gateway": interface.get("IPv4Gateway"),
            },
            "raw_ipv4_neighbors": len(ipv4_entries),
            "raw_ipv6_neighbors": len(ipv6_entries),
            "filtered_entries": filtered_out_count,
        }
        return observations

    def _validate_interface(self) -> dict:
        """Confirms `interface_index` still maps to `interface_alias` (spec
        section 2). Never silently switches interfaces: any mismatch raises
        `DiscoveryFixtureError` describing the new index and requiring the
        operator to update config/settings.yaml before retrying — that
        explicit edit-and-rerun step is this collector's "confirmación"
        gate for a non-interactive batch run.
        """
        config = self._config
        info = None
        if config.interface_index is not None:
            info = get_net_ip_configuration(config.interface_index, config.command_timeout_seconds, self._run_command)

        if info is not None and str(info.get("InterfaceAlias", "")).lower() == config.interface_alias.lower():
            return info

        by_alias = get_net_ip_configuration_by_alias(
            config.interface_alias, config.command_timeout_seconds, self._run_command
        )
        if by_alias is None:
            raise DiscoveryFixtureError(
                f"No se encontró ninguna interfaz con alias '{config.interface_alias}'. "
                "Verifica que esté conectada y tenga una IP asignada."
            )

        new_index = by_alias.get("InterfaceIndex")
        raise DiscoveryFixtureError(
            f"El índice configurado para '{config.interface_alias}' "
            f"({config.interface_index}) ya no coincide; el índice actual es {new_index}. "
            f"Actualiza discovery.interface_index a {new_index} en config/settings.yaml y vuelve a ejecutar."
        )

    def _filter(
        self, entries: list[dict], interface: dict, own_addresses: set[str]
    ) -> tuple[list[dict], int]:
        kept: list[dict] = []
        dropped = 0
        for entry in entries:
            if self._should_keep(entry, own_addresses):
                kept.append(entry)
            else:
                dropped += 1
        return kept, dropped

    @staticmethod
    def _should_keep(entry: dict, own_addresses: set[str]) -> bool:
        raw_ip = str(entry.get("IPAddress") or "").strip()
        raw_mac = str(entry.get("LinkLayerAddress") or "").strip().upper()
        state = str(entry.get("State") or "")

        if not raw_ip or not raw_mac:
            return False
        if raw_mac in (_ZERO_MAC, _BROADCAST_MAC):
            return False
        if raw_mac.startswith("01-00-5E") or raw_mac.startswith("33-33-"):
            return False  # IPv4/IPv6 multicast MAC ranges

        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            return False

        if isinstance(ip, ipaddress.IPv4Address) and ip in _IPV4_MULTICAST_NET:
            return False
        if isinstance(ip, ipaddress.IPv6Address) and ip in _IPV6_MULTICAST_NET:
            return False
        if raw_ip in own_addresses:
            return False
        if state not in _ACTIVE_STATES:
            # Unreachable/Incomplete/Permanent: never becomes an active device.
            return False
        return True

    @staticmethod
    def _group_by_mac(entries: list[dict]) -> list[dict]:
        candidates: dict[str, dict] = {}
        for entry in entries:
            mac = str(entry["LinkLayerAddress"]).strip().upper()
            ip = str(entry["IPAddress"]).strip()
            candidate = candidates.setdefault(mac, {"mac": mac, "ipv4": None, "ipv6": [], "states": []})
            candidate["states"].append(str(entry.get("State")))
            try:
                parsed = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if isinstance(parsed, ipaddress.IPv4Address):
                candidate["ipv4"] = ip
            else:
                if ip not in candidate["ipv6"]:
                    candidate["ipv6"].append(ip)
        return list(candidates.values())

    def _build_observation(self, candidate: dict, interface_index: int, observed_at: datetime) -> RawDiscoveryObservation:
        config = self._config
        probe_ip = candidate.get("ipv4") or (candidate["ipv6"][0] if candidate["ipv6"] else None)

        hostname = None
        if probe_ip:
            hostname = resolve_dns_name(probe_ip, config.command_timeout_seconds, self._run_command)

        classification = self._classify(candidate, probe_ip, hostname)

        payload: dict = {
            "mac": candidate["mac"],
            "interface_index": interface_index,
            "neighbor_states": candidate["states"],
            "device_type_hint": classification.device_type.value,
            "classification_confidence": classification.confidence,
            "classification_evidence": classification.evidence_notes,
        }
        if candidate.get("ipv4"):
            payload["ipv4"] = candidate["ipv4"]
        if candidate.get("ipv6"):
            payload["ipv6"] = candidate["ipv6"]
        if hostname:
            payload["hostname"] = hostname
        if classification.manufacturer:
            payload["manufacturer_hint"] = classification.manufacturer

        observation_type = ObservationType.IPV4_NEIGHBOR if candidate.get("ipv4") else ObservationType.IPV6_NEIGHBOR
        return RawDiscoveryObservation(
            collector_id="collector-windows-neighbor",
            collector_type=self.collector_type,
            observed_at=observed_at,
            observation_type=observation_type,
            source=f"windows-neighbor:{candidate['mac']}",
            raw_payload=payload,
        )

    def _classify(self, candidate: dict, probe_ip: str | None, hostname: str | None):
        evidence = ClassificationEvidence(ptr_hostname=hostname)
        if self._config.allow_active_enrichment and probe_ip:
            open_ports = {
                port
                for port in self._config.allowed_probe_ports
                if test_net_connection(probe_ip, port, self._config.command_timeout_seconds, self._run_command)
            }
            evidence.open_ports = open_ports
            if 22 in open_ports:
                evidence.ssh_banner = ssh_keyscan(probe_ip, self._config.command_timeout_seconds, self._run_command)
            if 80 in open_ports:
                head = curl_head(probe_ip, 80, False, self._config.command_timeout_seconds, self._run_command)
                if head:
                    evidence.http_headers = head.get("headers", {})
                luci = curl_head(
                    probe_ip, 80, False, self._config.command_timeout_seconds, self._run_command, path="/cgi-bin/luci/"
                )
                evidence.luci_reachable = bool(luci and luci.get("status_code") in (200, 302, 401))
        return classify(evidence)


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]
