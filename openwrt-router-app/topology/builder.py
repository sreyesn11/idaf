from __future__ import annotations

from diagnostics.enums import DiagnosticState
from discovery.enums import DeviceDiscoveryStatus
from discovery.repositories.inventory_device_repository import InventoryDeviceRecord
from discovery.repositories.topology_link_repository import TopologyLinkRecord
from topology.models import TopologyGraph, TopologyLink, TopologyNode

PC_NODE_ID = "pc-desarrollo"

# TopologyNode.state is typed as DiagnosticState (the rendering vocabulary
# the existing 2-node diagram already uses); inventory devices don't have a
# diagnostic run of their own, so this is a rough visual-only mapping from
# discovery/management status to the closest state color — never a real
# health signal. APPROVED devices render HEALTHY unless they're MANAGED and
# have an actual diagnostic (the caller can override via `state_overrides`).
_DISCOVERY_STATUS_TO_DIAGNOSTIC_STATE = {
    DeviceDiscoveryStatus.APPROVED.value: DiagnosticState.HEALTHY,
    DeviceDiscoveryStatus.PENDING_APPROVAL.value: DiagnosticState.UNKNOWN,
    DeviceDiscoveryStatus.DISCOVERED.value: DiagnosticState.UNKNOWN,
    DeviceDiscoveryStatus.STALE.value: DiagnosticState.WARNING,
    DeviceDiscoveryStatus.IGNORED.value: DiagnosticState.UNKNOWN,
    DeviceDiscoveryStatus.REMOVED.value: DiagnosticState.UNKNOWN,
}


def build_pc_to_router_topology(
    device_alias: str, router_host: str, latest_state: DiagnosticState | None
) -> TopologyGraph:
    """Build the minimal 'PC Desarrollo -> OpenWrt One' topology graph.

    The router's node/link state mirrors its latest diagnostic result
    (UNKNOWN if no diagnostic has been run yet for this device).
    """
    router_state = latest_state or DiagnosticState.UNKNOWN

    pc_node = TopologyNode(
        id=PC_NODE_ID,
        label="PC Desarrollo",
        type="dev_machine",
        state=DiagnosticState.HEALTHY,
    )
    router_node = TopologyNode(
        id=device_alias,
        label=f"{device_alias} ({router_host})",
        type="openwrt_router",
        state=router_state,
        metadata={"host": router_host},
    )
    link = TopologyLink(
        source=PC_NODE_ID,
        target=device_alias,
        type="ssh",
        state=router_state,
    )
    return TopologyGraph(nodes=[pc_node, router_node], links=[link])


def build_inventory_topology(
    devices: list[InventoryDeviceRecord],
    links: list[TopologyLinkRecord],
    *,
    include_pending: bool = True,
) -> TopologyGraph:
    """Build a graph from the discovery inventory: approved/managed devices,
    optionally pending ones, and their persisted parent-child links (spec
    section 15). Ignored and removed/merged devices are never shown — a mere
    shared IP was never enough to create a `TopologyLinkRecord` in the first
    place (see `discovery_service._link_parent`), so nothing here is an IP
    coincidence being mistaken for a real link.
    """
    visible_statuses = {DeviceDiscoveryStatus.APPROVED.value, DeviceDiscoveryStatus.STALE.value}
    if include_pending:
        visible_statuses.add(DeviceDiscoveryStatus.PENDING_APPROVAL.value)

    visible_devices = [d for d in devices if d.discovery_status in visible_statuses]
    visible_ids = {d.id for d in visible_devices}

    nodes = [
        TopologyNode(
            id=str(device.id),
            label=f"{device.name} ({device.alias})" if device.name != device.alias else device.name,
            type=device.device_type.lower(),
            state=_DISCOVERY_STATUS_TO_DIAGNOSTIC_STATE.get(device.discovery_status, DiagnosticState.UNKNOWN),
            metadata={
                "estado_descubrimiento": device.discovery_status,
                "gestion": device.management_status,
                "fabricante": device.manufacturer or "",
            },
        )
        for device in visible_devices
    ]

    topology_links = [
        TopologyLink(
            source=str(link.source_device_id),
            target=str(link.target_device_id),
            type=link.link_type.lower(),
            state=DiagnosticState.HEALTHY,
        )
        for link in links
        if link.source_device_id in visible_ids and link.target_device_id in visible_ids
    ]

    return TopologyGraph(nodes=nodes, links=topology_links)
