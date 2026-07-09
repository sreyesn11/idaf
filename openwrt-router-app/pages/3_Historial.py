from __future__ import annotations

import json

import streamlit as st

from core.constants import APP_NAME
from diagnostics.enums import DiagnosticState
from models.execution import ExecutionStatus
from repositories.diagnostic_repository import DiagnosticRepository
from repositories.execution_repository import ExecutionRepository

st.set_page_config(page_title=f"Historial — {APP_NAME}", page_icon="🗂️", layout="wide")


@st.cache_resource
def get_execution_repository() -> ExecutionRepository:
    return ExecutionRepository()


@st.cache_resource
def get_diagnostic_repository() -> DiagnosticRepository:
    return DiagnosticRepository()


st.title("Historial")

tab_executions, tab_diagnostics = st.tabs(["Ejecuciones", "Diagnósticos"])


def _render_executions_tab() -> None:
    repository = get_execution_repository()

    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Estado", ["Todos"] + [s.value for s in ExecutionStatus], key="exec_status")
    with col2:
        categories = sorted({record.category for record in repository.list_all()})
        category_filter = st.selectbox("Categoría", ["Todas"] + categories, key="exec_category")
    with col3:
        search = st.text_input("Buscar por comando", key="exec_search")

    records = repository.list_all(
        status=None if status_filter == "Todos" else status_filter,
        category=None if category_filter == "Todas" else category_filter,
        search=search or None,
    )

    if not records:
        st.info("No hay ejecuciones registradas con los filtros seleccionados.")
        return

    table_rows = [
        {
            "ID": record.execution_id,
            "Fecha": record.started_at,
            "Host": record.host,
            "Usuario": record.username,
            "Comando": record.command_name,
            "Categoría": record.category,
            "Estado": record.status,
            "Código de salida": record.exit_code,
            "Duración (s)": record.duration_seconds,
        }
        for record in records
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    execution_ids = [record.execution_id for record in records]
    selected_id = st.selectbox("Ver detalle de ejecución", execution_ids, key="exec_detail_select")
    selected_record = next(r for r in records if r.execution_id == selected_id)

    with st.expander(f"Detalle de {selected_record.execution_id}", expanded=True):
        st.write(f"**Comando:** `{selected_record.command}`")
        st.write(f"**Estado:** {selected_record.status}")
        st.write(f"**Mensaje:** {selected_record.user_message}")
        if selected_record.technical_message:
            st.caption(f"Detalle técnico: {selected_record.technical_message}")

        tab_stdout, tab_stderr, tab_parsed = st.tabs(["stdout", "stderr", "Datos estructurados"])
        with tab_stdout:
            st.code(selected_record.stdout or "(sin salida)")
        with tab_stderr:
            st.code(selected_record.stderr or "(sin salida)")
        with tab_parsed:
            if selected_record.parsed_data_json:
                st.json(json.loads(selected_record.parsed_data_json))
            else:
                st.info("No hay datos estructurados disponibles.")

        if selected_record.evidence_path:
            try:
                with open(selected_record.evidence_path, "r", encoding="utf-8") as f:
                    evidence_content = f.read()
                st.download_button(
                    "Descargar evidencia JSON",
                    data=evidence_content,
                    file_name=f"{selected_record.execution_id}.json",
                    mime="application/json",
                    key=f"download_exec_{selected_record.execution_id}",
                )
            except OSError:
                st.warning("El archivo de evidencia no está disponible.")

        if st.button("Eliminar este registro", key=f"delete_exec_{selected_record.execution_id}"):
            repository.delete_by_execution_id(selected_record.execution_id)
            st.success("Registro eliminado.")
            st.rerun()

    st.divider()
    confirm_clear = st.checkbox("Confirmo que deseo eliminar todo el historial de ejecuciones", key="exec_confirm_clear")
    if st.button("Limpiar historial de ejecuciones", disabled=not confirm_clear, key="exec_clear_button"):
        repository.clear_all()
        st.success("Historial de ejecuciones eliminado.")
        st.rerun()


def _render_diagnostics_tab() -> None:
    repository = get_diagnostic_repository()

    col1, col2 = st.columns(2)
    with col1:
        state_filter = st.selectbox("Estado", ["Todos"] + [s.value for s in DiagnosticState], key="diag_status")
    with col2:
        search = st.text_input("Buscar por host o resumen", key="diag_search")

    records = repository.list_all(
        state=None if state_filter == "Todos" else state_filter,
        search=search or None,
    )

    if not records:
        st.info("No hay diagnósticos registrados con los filtros seleccionados.")
        return

    table_rows = [
        {
            "ID": record.diagnostic_id,
            "Fecha": record.started_at,
            "Host": record.target,
            "Estado": record.state,
            "Resumen": record.summary,
            "Duración (s)": record.duration_seconds,
        }
        for record in records
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    diagnostic_ids = [record.diagnostic_id for record in records]
    selected_id = st.selectbox("Ver detalle de diagnóstico", diagnostic_ids, key="diag_detail_select")
    selected_record = next(r for r in records if r.diagnostic_id == selected_id)

    with st.expander(f"Detalle de {selected_record.diagnostic_id}", expanded=True):
        st.write(f"**Host:** {selected_record.target}")
        st.write(f"**Estado:** {selected_record.state}")
        st.write(f"**Resumen:** {selected_record.summary}")

        checks = json.loads(selected_record.checks_json)
        st.dataframe(
            [
                {
                    "Chequeo": c["check_name"],
                    "Estado": c["state"],
                    "Valor": c.get("value"),
                    "Resumen": c["summary"],
                }
                for c in checks
            ],
            use_container_width=True,
            hide_index=True,
        )

        warnings = json.loads(selected_record.warnings_json)
        for warning in warnings:
            st.caption(f"⚠️ {warning}")

        if selected_record.evidence_path:
            try:
                with open(selected_record.evidence_path, "r", encoding="utf-8") as f:
                    evidence_content = f.read()
                st.download_button(
                    "Descargar diagnóstico JSON",
                    data=evidence_content,
                    file_name=f"{selected_record.diagnostic_id}.json",
                    mime="application/json",
                    key=f"download_diag_{selected_record.diagnostic_id}",
                )
            except OSError:
                st.warning("El archivo de evidencia no está disponible.")

        if st.button("Eliminar este diagnóstico", key=f"delete_diag_{selected_record.diagnostic_id}"):
            repository.delete_by_diagnostic_id(selected_record.diagnostic_id)
            st.success("Diagnóstico eliminado.")
            st.rerun()

    st.divider()
    confirm_clear = st.checkbox("Confirmo que deseo eliminar todo el historial de diagnósticos", key="diag_confirm_clear")
    if st.button("Limpiar historial de diagnósticos", disabled=not confirm_clear, key="diag_clear_button"):
        repository.clear_all()
        st.success("Historial de diagnósticos eliminado.")
        st.rerun()


with tab_executions:
    _render_executions_tab()

with tab_diagnostics:
    _render_diagnostics_tab()
