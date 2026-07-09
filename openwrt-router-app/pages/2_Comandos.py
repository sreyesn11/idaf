from __future__ import annotations

import json

import streamlit as st

from core.command_service import CommandService
from core.constants import APP_NAME, SESSION_CONNECTION_CONFIG, SESSION_LAST_RESULT
from core.execution_service import ExecutionService
from models.connection import ConnectionConfig
from repositories.execution_repository import ExecutionRepository

st.set_page_config(page_title=f"Comandos — {APP_NAME}", page_icon="🛠️", layout="wide")


@st.cache_resource
def get_command_service() -> CommandService:
    return CommandService()


@st.cache_resource
def get_execution_service() -> ExecutionService:
    return ExecutionService(repository=ExecutionRepository())


st.title("Comandos disponibles")

connection: ConnectionConfig | None = st.session_state.get(SESSION_CONNECTION_CONFIG)
if connection is None:
    st.warning("Primero prueba la conexión en la sección **Conexión**.")
    st.stop()

command_service = get_command_service()
execution_service = get_execution_service()

categories = ["Todas"] + command_service.list_categories()
selected_category = st.selectbox("Categoría", categories)

commands = command_service.list_commands(category=None if selected_category == "Todas" else selected_category)

if not commands:
    st.info("No hay comandos habilitados para esta categoría.")
    st.stop()

options = {f"{c.name} ({c.id})": c.id for c in commands}
selected_label = st.selectbox("Comando", list(options.keys()))
selected_command = command_service.get_by_id(options[selected_label])

st.markdown(f"**Descripción:** {selected_command.description}")
st.code(selected_command.command, language="bash")
st.write(f"Timeout: {selected_command.timeout} s · Categoría: {selected_command.category}")

if st.button("Ejecutar"):
    with st.spinner("Ejecutando comando en el router..."):
        try:
            result = execution_service.run(connection, selected_command)
        except Exception:
            st.error("Ocurrió un error inesperado al ejecutar el comando.")
        else:
            st.session_state[SESSION_LAST_RESULT] = json.loads(result.model_dump_json())

st.divider()
st.subheader("Resultado")

last_result = st.session_state.get(SESSION_LAST_RESULT)
if last_result is None:
    st.info("Todavía no se ha ejecutado ningún comando en esta sesión.")
else:
    status = last_result["status"]
    if status == "COMPLETED":
        st.success(last_result["user_message"])
    elif status == "COMPLETED_WITH_WARNINGS":
        st.warning(last_result["user_message"])
    else:
        st.error(last_result["user_message"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Estado", status)
    col2.metric("Código de salida", last_result["exit_code"] if last_result["exit_code"] is not None else "-")
    col3.metric(
        "Duración (s)",
        last_result["duration_seconds"] if last_result["duration_seconds"] is not None else "-",
    )
    col4.metric("Fecha", last_result["started_at"])

    if last_result.get("technical_message"):
        st.caption(f"Detalle técnico: {last_result['technical_message']}")

    tab_stdout, tab_stderr, tab_parsed = st.tabs(["stdout", "stderr", "Datos estructurados"])
    with tab_stdout:
        st.code(last_result["stdout"] or "(sin salida)")
    with tab_stderr:
        st.code(last_result["stderr"] or "(sin salida)")
    with tab_parsed:
        if last_result["parsed_data"] is not None:
            st.json(last_result["parsed_data"])
        else:
            st.info("No hay datos estructurados disponibles.")

    st.download_button(
        "Descargar evidencia JSON",
        data=json.dumps(last_result, ensure_ascii=False, indent=2),
        file_name=f"{last_result['execution_id']}.json",
        mime="application/json",
    )
