from __future__ import annotations

import streamlit as st

from core.constants import (
    APP_NAME,
    APP_VERSION,
    SESSION_CONNECTED_DEVICES,
    SESSION_LAST_RESULT,
)
from core.branding import apply_branding
from core.formatting import format_datetime
from core.icons import ICONS
from core.logging_config import configure_logging
from events.event_repository import EventRepository
from repositories.diagnostic_repository import DiagnosticRepository
from repositories.execution_repository import ExecutionRepository

configure_logging()

st.set_page_config(page_title=APP_NAME, page_icon=ICONS["home"], layout="wide")
apply_branding()


@st.cache_resource
def get_execution_repository() -> ExecutionRepository:
    return ExecutionRepository()


@st.cache_resource
def get_diagnostic_repository() -> DiagnosticRepository:
    return DiagnosticRepository()


@st.cache_resource
def get_event_repository() -> EventRepository:
    return EventRepository()


def main() -> None:
    st.title(f"{ICONS['home']} {APP_NAME}")
    st.caption(
        "Módulo de administración y diagnóstico del router OpenWrt — primera fase de la "
        "arquitectura de observabilidad de la tesis IDAF."
    )

    repository = get_execution_repository()
    stats = repository.stats()

    connected_devices = st.session_state.get(SESSION_CONNECTED_DEVICES, {})
    last_result = st.session_state.get(SESSION_LAST_RESULT)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"{ICONS['devices']} Dispositivos conectados", len(connected_devices))
    col2.metric(f"{ICONS['commands']} Total de ejecuciones", stats["total"])
    col3.metric(f"{ICONS['success']} Ejecuciones exitosas", stats["successful"])
    col4.metric(f"{ICONS['error']} Ejecuciones fallidas", stats["failed"])

    st.subheader(f"{ICONS['commands']} Último comando ejecutado")
    if last_result is not None:
        st.write(f"**{last_result['command_name']}** — estado `{last_result['status']}`")
    else:
        st.write("Todavía no se ha ejecutado ningún comando en esta sesión.")

    st.divider()

    diagnostic_repository = get_diagnostic_repository()
    diagnostic_stats = diagnostic_repository.stats()
    latest_diagnostic = diagnostic_stats["latest"]

    st.subheader(f"{ICONS['diagnostics']} Diagnóstico")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"{ICONS['list']} Total de diagnósticos", diagnostic_stats["total"])
    col2.metric(f"{ICONS['healthy']} Saludables", diagnostic_stats["healthy"])
    col3.metric(f"{ICONS['warning']} Con advertencia", diagnostic_stats["warning"])
    col4.metric(f"{ICONS['critical']} Degradados/críticos", diagnostic_stats["degraded_or_critical"])

    if latest_diagnostic is not None:
        st.write(
            f"**Último diagnóstico:** estado `{latest_diagnostic.state}` "
            f"— {format_datetime(latest_diagnostic.started_at)}"
        )
        st.caption(latest_diagnostic.summary)
    else:
        st.write("Todavía no se ha ejecutado ningún diagnóstico.")

    latest_event = get_event_repository().stats()["latest"]
    if latest_event is not None:
        st.caption(
            f"{ICONS['event']} Último evento: {latest_event.target_device_id} pasó de "
            f"`{latest_event.from_state}` a `{latest_event.to_state}` "
            f"— {format_datetime(latest_event.timestamp)}"
        )

    st.divider()
    st.caption(f"Versión: {APP_VERSION}")
    st.info(
        "Usa el menú lateral para configurar la conexión, ejecutar comandos predefinidos, "
        "correr el diagnóstico general del router y revisar el historial."
    )


# st.navigation()/st.Page(icon=...) instead of the classic auto-discovered
# pages/ folder: it's the only supported way to put an icon next to each
# section in the sidebar nav (page_icon only sets the browser tab favicon).
pages = [
    st.Page(main, title="Inicio", icon=ICONS["home"], default=True),
    st.Page("pages/1_Conexion.py", title="Conexión", icon=ICONS["connection"]),
    st.Page("pages/2_Comandos.py", title="Comandos", icon=ICONS["commands"]),
    st.Page("pages/3_Historial.py", title="Historial", icon=ICONS["history"]),
    st.Page("pages/4_Diagnostico.py", title="Diagnóstico", icon=ICONS["diagnostics"]),
    st.Page("pages/5_Topologia.py", title="Topología", icon=ICONS["topology"]),
    st.Page("pages/7_Descubrimiento.py", title="Descubrimiento", icon=ICONS["discovery"]),
    st.Page("pages/6_Acerca_de.py", title="Acerca de", icon=ICONS["about"]),
]

st.navigation(pages).run()
