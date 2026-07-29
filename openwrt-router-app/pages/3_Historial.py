from __future__ import annotations

import json

import streamlit as st

from core.branding import state_badge
from core.formatting import format_datetime
from core.icons import ICONS
from diagnostics.enums import DiagnosticState
from events.event_repository import EventRepository
from models.execution import ExecutionStatus
from repositories.device_repository import DeviceRepository
from repositories.diagnostic_repository import DiagnosticRepository
from repositories.execution_repository import ExecutionRepository



@st.cache_resource
def get_execution_repository() -> ExecutionRepository:
    return ExecutionRepository()


@st.cache_resource
def get_diagnostic_repository() -> DiagnosticRepository:
    return DiagnosticRepository()


@st.cache_resource
def get_device_repository() -> DeviceRepository:
    return DeviceRepository()


@st.cache_resource
def get_event_repository() -> EventRepository:
    return EventRepository()


def _device_alias_map() -> dict[int, str]:
    return {d.id: d.alias for d in get_device_repository().list_all()}


st.title(f"{ICONS['history']} Historial")

tab_executions, tab_diagnostics, tab_events = st.tabs(
    [f"{ICONS['commands']} Ejecuciones", f"{ICONS['diagnostics']} Diagnósticos", f"{ICONS['event']} Eventos"]
)


def _render_executions_tab() -> None:
    repository = get_execution_repository()
    alias_by_device_id = _device_alias_map()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status_filter = st.selectbox("Estado", ["Todos"] + [s.value for s in ExecutionStatus], key="exec_status")
    with col2:
        categories = sorted({record.category for record in repository.list_all()})
        category_filter = st.selectbox("Categoría", ["Todas"] + categories, key="exec_category")
    with col3:
        device_options = {"Todos": None} | {alias: device_id for device_id, alias in alias_by_device_id.items()}
        device_filter_label = st.selectbox("Dispositivo", list(device_options.keys()), key="exec_device")
    with col4:
        search = st.text_input("Buscar por comando", key="exec_search")

    records = repository.list_all(
        status=None if status_filter == "Todos" else status_filter,
        category=None if category_filter == "Todas" else category_filter,
        device_id=device_options[device_filter_label],
        search=search or None,
    )

    if not records:
        st.info("No hay ejecuciones registradas con los filtros seleccionados.")
        return

    table_rows = [
        {
            "ID": record.execution_id,
            "Fecha": format_datetime(record.started_at),
            "Dispositivo": alias_by_device_id.get(record.device_id, record.host),
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

    with st.expander(f"{ICONS['search']} Detalle de {selected_record.execution_id}", expanded=True):
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
                    f"{ICONS['download']} Descargar evidencia JSON",
                    data=evidence_content,
                    file_name=f"{selected_record.execution_id}.json",
                    mime="application/json",
                    key=f"download_exec_{selected_record.execution_id}",
                )
            except OSError:
                st.warning("El archivo de evidencia no está disponible.")

        if st.button(f"{ICONS['delete']} Eliminar este registro", key=f"delete_exec_{selected_record.execution_id}"):
            repository.delete_by_execution_id(selected_record.execution_id)
            st.success("Registro eliminado.")
            st.rerun()

    st.divider()
    total_executions = repository.stats()["total"]
    confirm_clear = st.checkbox(
        f"Confirmo que deseo eliminar las **{total_executions}** ejecuciones del historial "
        "(no solo las filtradas arriba). Esta acción no se puede deshacer.",
        key="exec_confirm_clear",
    )
    if st.button(f"{ICONS['clear_all']} Limpiar historial de ejecuciones", disabled=not confirm_clear, key="exec_clear_button"):
        repository.clear_all()
        st.success("Historial de ejecuciones eliminado.")
        st.rerun()


def _render_diagnostics_tab() -> None:
    repository = get_diagnostic_repository()
    alias_by_device_id = _device_alias_map()

    col1, col2, col3 = st.columns(3)
    with col1:
        state_filter = st.selectbox("Estado", ["Todos"] + [s.value for s in DiagnosticState], key="diag_status")
    with col2:
        device_options = {"Todos": None} | {alias: device_id for device_id, alias in alias_by_device_id.items()}
        device_filter_label = st.selectbox("Dispositivo", list(device_options.keys()), key="diag_device")
    with col3:
        search = st.text_input("Buscar por host o resumen", key="diag_search")

    records = repository.list_all(
        state=None if state_filter == "Todos" else state_filter,
        device_id=device_options[device_filter_label],
        search=search or None,
    )

    if not records:
        st.info("No hay diagnósticos registrados con los filtros seleccionados.")
        return

    table_rows = [
        {
            "ID": record.diagnostic_id,
            "Fecha": format_datetime(record.started_at),
            "Dispositivo": alias_by_device_id.get(record.device_id, record.target_device_id),
            "Host": record.target_host,
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

    with st.expander(f"{ICONS['search']} Detalle de {selected_record.diagnostic_id}", expanded=True):
        st.write(f"**Dispositivo:** {selected_record.target_device_id}")
        st.write(f"**Host:** {selected_record.target_host}")
        st.markdown(f"**Estado:** {state_badge(selected_record.state)}", unsafe_allow_html=True)
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
            st.caption(f"{ICONS['warning']} {warning}")

        if selected_record.evidence_path:
            try:
                with open(selected_record.evidence_path, "r", encoding="utf-8") as f:
                    evidence_content = f.read()
                st.download_button(
                    f"{ICONS['download']} Descargar diagnóstico JSON",
                    data=evidence_content,
                    file_name=f"{selected_record.diagnostic_id}.json",
                    mime="application/json",
                    key=f"download_diag_{selected_record.diagnostic_id}",
                )
            except OSError:
                st.warning("El archivo de evidencia no está disponible.")

        if st.button(f"{ICONS['delete']} Eliminar este diagnóstico", key=f"delete_diag_{selected_record.diagnostic_id}"):
            repository.delete_by_diagnostic_id(selected_record.diagnostic_id)
            st.success("Diagnóstico eliminado.")
            st.rerun()

    st.divider()
    total_diagnostics = repository.stats()["total"]
    confirm_clear = st.checkbox(
        f"Confirmo que deseo eliminar los **{total_diagnostics}** diagnósticos del historial "
        "(no solo los filtrados arriba). Esta acción no se puede deshacer.",
        key="diag_confirm_clear",
    )
    if st.button(f"{ICONS['clear_all']} Limpiar historial de diagnósticos", disabled=not confirm_clear, key="diag_clear_button"):
        repository.clear_all()
        st.success("Historial de diagnósticos eliminado.")
        st.rerun()


def _render_events_tab() -> None:
    repository = get_event_repository()

    search = st.text_input("Buscar por dispositivo", key="event_search")
    records = repository.list_all(search=search or None)

    if not records:
        st.info("No hay eventos registrados con los filtros seleccionados.")
        return

    table_rows = [
        {
            "Fecha": format_datetime(record.timestamp),
            "Tipo": record.event_type,
            "Dispositivo": record.target_device_id,
            "Estado anterior": record.from_state,
            "Estado nuevo": record.to_state,
            "Fuente": record.source,
        }
        for record in records
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    st.divider()
    total_events = len(repository.list_all())
    confirm_clear = st.checkbox(
        f"Confirmo que deseo eliminar los **{total_events}** eventos del historial "
        "(no solo los filtrados arriba). Esta acción no se puede deshacer.",
        key="event_confirm_clear",
    )
    if st.button(f"{ICONS['clear_all']} Limpiar historial de eventos", disabled=not confirm_clear, key="event_clear_button"):
        repository.clear_all()
        st.success("Historial de eventos eliminado.")
        st.rerun()


with tab_executions:
    _render_executions_tab()

with tab_diagnostics:
    _render_diagnostics_tab()

with tab_events:
    _render_events_tab()
