from __future__ import annotations

import json

import streamlit as st

from core.constants import (
    APP_NAME,
    SESSION_CONNECTION_CONFIG,
    SESSION_CONNECTION_STATUS,
    SESSION_LAST_DIAGNOSTIC,
)
from core.exceptions import RouterAppError
from models.connection import ConnectionConfig
from workflows.router_general_health import run_router_general_health

st.set_page_config(page_title=f"Diagnóstico — {APP_NAME}", page_icon="🩺", layout="wide")

st.title("Diagnóstico general del router")
st.write(
    "Ejecuta automáticamente el diagnóstico **Router General Health**: valida la conexión SSH y "
    "consulta identidad, uptime, memoria, almacenamiento, LAN, WAN, IPv6 y Wi-Fi en una sola pasada."
)

connection: ConnectionConfig | None = st.session_state.get(SESSION_CONNECTION_CONFIG)

st.subheader("Información de conexión")
if connection is None:
    st.warning("Primero prueba la conexión en la sección **Conexión**.")
    st.stop()
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("Host", connection.host)
    col2.metric("Usuario", connection.username)
    col3.metric("Estado de validación", st.session_state.get(SESSION_CONNECTION_STATUS) or "Sin probar")

st.divider()

if st.button("Ejecutar diagnóstico", type="primary"):
    steps = st.empty()
    step_messages = [
        "Validando conexión...",
        "Consultando información del sistema...",
        "Evaluando memoria...",
        "Evaluando almacenamiento...",
        "Evaluando interfaces...",
        "Consolidando diagnóstico...",
    ]
    with st.spinner("\n".join(step_messages)):
        try:
            diagnostic = run_router_general_health(connection)
        except RouterAppError as exc:
            st.error(exc.friendly_message)
            if exc.detail:
                st.caption(f"Detalle técnico: {exc.detail}")
            diagnostic = None
        except Exception:
            st.error("Ocurrió un error inesperado al ejecutar el diagnóstico.")
            diagnostic = None
    steps.empty()

    if diagnostic is not None:
        st.session_state[SESSION_LAST_DIAGNOSTIC] = json.loads(diagnostic.model_dump_json())

st.subheader("Resultado general")
last_diagnostic = st.session_state.get(SESSION_LAST_DIAGNOSTIC)

if last_diagnostic is None:
    st.info("Todavía no se ha ejecutado ningún diagnóstico en esta sesión.")
else:
    state = last_diagnostic["state"]
    _STATE_RENDER = {
        "HEALTHY": st.success,
        "WARNING": st.warning,
        "DEGRADED": st.warning,
        "CRITICAL": st.error,
        "UNREACHABLE": st.error,
        "UNKNOWN": st.info,
    }
    render = _STATE_RENDER.get(state, st.info)
    render(f"Estado general: **{state}**\n\n{last_diagnostic['summary']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Duración (s)", last_diagnostic["duration_seconds"])
    col2.metric("Inicio", last_diagnostic["started_at"])
    col3.metric("Host", last_diagnostic["target"])

    if last_diagnostic.get("warnings"):
        for warning in last_diagnostic["warnings"]:
            st.caption(f"⚠️ {warning}")

    st.subheader("Chequeos")
    rows = [
        {
            "Chequeo": check["check_name"],
            "Estado": check["state"],
            "Valor": check["value"],
            "Resumen": check["summary"],
        }
        for check in last_diagnostic["checks"]
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("Evidencia")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "Descargar diagnóstico JSON",
            data=json.dumps(last_diagnostic, ensure_ascii=False, indent=2),
            file_name=f"{last_diagnostic['diagnostic_id']}.json",
            mime="application/json",
        )
    with col2:
        st.caption("Ejecuciones relacionadas:")
        st.code("\n".join(last_diagnostic["evidence_execution_ids"]) or "(ninguna)")
    with col3:
        st.page_link("pages/3_Historial.py", label="Abrir historial", icon="🗂️")
