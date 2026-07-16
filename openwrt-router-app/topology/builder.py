from __future__ import annotations

from diagnostics.enums import DiagnosticState
from topology.models import TopologyGraph, TopologyLink, TopologyNode

PC_NODE_ID = "pc-desarrollo"


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
