from __future__ import annotations

import streamlit as st

from core.constants import (
    APP_NAME,
    APP_VERSION,
    SESSION_CONNECTION_STATUS,
    SESSION_LAST_RESULT,
)
from core.logging_config import configure_logging
from repositories.diagnostic_repository import DiagnosticRepository
from repositories.execution_repository import ExecutionRepository

configure_logging()

st.set_page_config(page_title=APP_NAME, page_icon="📡", layout="wide")


@st.cache_resource
def get_execution_repository() -> ExecutionRepository:
    return ExecutionRepository()


@st.cache_resource
def get_diagnostic_repository() -> DiagnosticRepository:
    return DiagnosticRepository()


def main() -> None:
    st.title(APP_NAME)
    st.caption(
        "Módulo de administración y diagnóstico del router OpenWrt — primera fase de la "
        "arquitectura de observabilidad de la tesis IDAF."
    )

    repository = get_execution_repository()
    stats = repository.stats()

    connection_status = st.session_state.get(SESSION_CONNECTION_STATUS)
    last_result = st.session_state.get(SESSION_LAST_RESULT)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Estado de conexión", connection_status or "Sin probar")
    col2.metric("Total de ejecuciones", stats["total"])
    col3.metric("Ejecuciones exitosas", stats["successful"])
    col4.metric("Ejecuciones fallidas", stats["failed"])

    st.subheader("Último comando ejecutado")
    if last_result is not None:
        st.write(f"**{last_result['command_name']}** — estado `{last_result['status']}`")
    else:
        st.write("Todavía no se ha ejecutado ningún comando en esta sesión.")

    st.divider()

    diagnostic_repository = get_diagnostic_repository()
    diagnostic_stats = diagnostic_repository.stats()
    latest_diagnostic = diagnostic_stats["latest"]

    st.subheader("Diagnóstico")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de diagnósticos", diagnostic_stats["total"])
    col2.metric("Saludables", diagnostic_stats["healthy"])
    col3.metric("Con advertencia", diagnostic_stats["warning"])
    col4.metric("Degradados/críticos", diagnostic_stats["degraded_or_critical"])

    if latest_diagnostic is not None:
        st.write(f"**Último diagnóstico:** estado `{latest_diagnostic.state}` — {latest_diagnostic.started_at}")
        st.caption(latest_diagnostic.summary)
    else:
        st.write("Todavía no se ha ejecutado ningún diagnóstico.")

    st.divider()
    st.caption(f"Versión: {APP_VERSION}")
    st.info(
        "Usa el menú lateral para configurar la conexión, ejecutar comandos predefinidos, "
        "correr el diagnóstico general del router y revisar el historial."
    )


main()
