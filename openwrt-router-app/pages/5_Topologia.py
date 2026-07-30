from __future__ import annotations

import streamlit as st

from core.formatting import format_datetime
from core.icons import ICONS
from diagnostics.enums import DiagnosticState
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository
from discovery.repositories.topology_link_repository import TopologyLinkRepository
from repositories.device_repository import DeviceRepository
from repositories.diagnostic_repository import DiagnosticRepository
from topology.builder import build_inventory_topology, build_pc_to_router_topology
from topology.renderer import render_inventory_tree, render_topology


@st.cache_resource
def get_device_repository() -> DeviceRepository:
    return DeviceRepository()


@st.cache_resource
def get_diagnostic_repository() -> DiagnosticRepository:
    return DiagnosticRepository()


@st.cache_resource
def get_inventory_device_repository() -> InventoryDeviceRepository:
    return InventoryDeviceRepository()


@st.cache_resource
def get_topology_link_repository() -> TopologyLinkRepository:
    return TopologyLinkRepository()


st.title(f"{ICONS['topology']} Topología")
st.write(
    "Topología mínima del laboratorio: la conexión entre este equipo de desarrollo y el "
    "router OpenWrt gestionado, coloreada según el último diagnóstico disponible para el "
    "dispositivo seleccionado."
)

devices = get_device_repository().list_all()
if not devices:
    st.info("Todavía no hay dispositivos guardados en la sección **Conexión**.")
else:
    options = {d.alias: d for d in devices}
    selected_alias = st.selectbox("Dispositivo", list(options.keys()))
    selected_device = options[selected_alias]

    latest_diagnostic = get_diagnostic_repository().get_latest_for_target(selected_device.alias)
    latest_state = DiagnosticState(latest_diagnostic.state) if latest_diagnostic is not None else None

    graph = build_pc_to_router_topology(selected_device.alias, selected_device.host, latest_state)
    render_topology(graph)

    if latest_diagnostic is not None:
        st.caption(
            f"Último diagnóstico: {format_datetime(latest_diagnostic.started_at)} — {latest_diagnostic.summary}"
        )
    else:
        st.caption("Todavía no se ha ejecutado ningún diagnóstico para este dispositivo.")

st.divider()
st.subheader(f"{ICONS['inventory']} Topología de inventario (descubrimiento)")
st.write(
    "Dispositivos aprobados y pendientes del módulo de **Descubrimiento**, con las relaciones "
    "padre-hijo detectadas (gateway → nodo). Un enlace aquí siempre proviene de un "
    "`TopologyLink` persistido — nunca de una simple coincidencia de IP."
)

include_pending = st.checkbox("Incluir dispositivos pendientes de aprobación", value=True)

inventory_devices = get_inventory_device_repository().list_all()
if not inventory_devices:
    st.info("Todavía no hay dispositivos en el inventario. Ejecuta un descubrimiento en la sección **Descubrimiento**.")
else:
    topology_links = get_topology_link_repository().list_all()
    inventory_graph = build_inventory_topology(inventory_devices, topology_links, include_pending=include_pending)
    render_inventory_tree(inventory_graph)
