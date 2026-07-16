from __future__ import annotations

from diagnostics.enums import DiagnosticState
from topology.builder import build_pc_to_router_topology


def test_topology_has_two_nodes_and_one_link() -> None:
    graph = build_pc_to_router_topology("lab-gateway-1", "192.168.1.1", DiagnosticState.HEALTHY)

    assert len(graph.nodes) == 2
    assert len(graph.links) == 1


def test_router_node_reflects_latest_diagnostic_state() -> None:
    graph = build_pc_to_router_topology("lab-gateway-1", "192.168.1.1", DiagnosticState.CRITICAL)

    router_node = graph.nodes[1]
    link = graph.links[0]
    assert router_node.state == DiagnosticState.CRITICAL
    assert link.state == DiagnosticState.CRITICAL


def test_router_node_is_unknown_when_no_diagnostic_exists() -> None:
    graph = build_pc_to_router_topology("lab-gateway-1", "192.168.1.1", None)

    router_node = graph.nodes[1]
    assert router_node.state == DiagnosticState.UNKNOWN


def test_pc_node_is_always_healthy() -> None:
    graph = build_pc_to_router_topology("lab-gateway-1", "192.168.1.1", DiagnosticState.CRITICAL)

    pc_node = graph.nodes[0]
    assert pc_node.state == DiagnosticState.HEALTHY
    assert pc_node.type == "dev_machine"


def test_link_connects_pc_to_router() -> None:
    graph = build_pc_to_router_topology("lab-gateway-1", "192.168.1.1", DiagnosticState.HEALTHY)

    link = graph.links[0]
    assert link.source == graph.nodes[0].id
    assert link.target == "lab-gateway-1"
