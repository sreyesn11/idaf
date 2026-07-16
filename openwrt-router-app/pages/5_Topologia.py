from __future__ import annotations

import streamlit as st

from core.branding import apply_branding
from core.constants import APP_NAME
from core.formatting import format_datetime
from core.icons import ICONS
from diagnostics.enums import DiagnosticState
from repositories.device_repository import DeviceRepository
from repositories.diagnostic_repository import DiagnosticRepository
from topology.builder import build_pc_to_router_topology
from topology.renderer import render_topology

st.set_page_config(page_title=f"Topología — {APP_NAME}", page_icon=ICONS["topology"], layout="wide")
apply_branding()


@st.cache_resource
def get_device_repository() -> DeviceRepository:
    return DeviceRepository()


@st.cache_resource
def get_diagnostic_repository() -> DiagnosticRepository:
    return DiagnosticRepository()


st.title(f"{ICONS['topology']} Topología")
st.write(
    "Topología mínima del laboratorio: la conexión entre este equipo de desarrollo y el "
    "router OpenWrt gestionado, coloreada según el último diagnóstico disponible para el "
    "dispositivo seleccionado."
)

devices = get_device_repository().list_all()
if not devices:
    st.info("Todavía no hay dispositivos guardados en la sección **Conexión**.")
    st.stop()

options = {d.alias: d for d in devices}
selected_alias = st.selectbox("Dispositivo", list(options.keys()))
selected_device = options[selected_alias]

latest_diagnostic = get_diagnostic_repository().get_latest_for_target(selected_device.alias)
latest_state = DiagnosticState(latest_diagnostic.state) if latest_diagnostic is not None else None

graph = build_pc_to_router_topology(selected_device.alias, selected_device.host, latest_state)
render_topology(graph)

if latest_diagnostic is not None:
    st.caption(f"Último diagnóstico: {format_datetime(latest_diagnostic.started_at)} — {latest_diagnostic.summary}")
else:
    st.caption("Todavía no se ha ejecutado ningún diagnóstico para este dispositivo.")
