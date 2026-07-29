from __future__ import annotations

import json

import streamlit as st

from core.branding import state_badge
from core.concurrency import get_device_lock_registry
from core.constants import SESSION_CONNECTED_DEVICES, SESSION_DIAGNOSTIC_RESULTS
from core.exceptions import RouterAppError
from core.formatting import format_datetime
from core.icons import ICONS
from workflows.router_general_health import run_router_general_health

st.title(f"{ICONS['diagnostics']} Diagnóstico general del router")
st.write(
    "Ejecuta automáticamente el diagnóstico **Router General Health**: valida la conexión SSH y "
    "consulta identidad, uptime, memoria, almacenamiento, LAN, WAN, IPv6 y Wi-Fi en una sola pasada. "
    "Puedes seleccionar varios dispositivos conectados; se diagnostican uno por uno, en orden, "
    "para no saturar ningún router. Cada resultado se muestra por separado."
)

connected = st.session_state.get(SESSION_CONNECTED_DEVICES, {})
if not connected:
    st.warning("Primero conecta al menos un dispositivo en la sección **Conexión**.")
    st.stop()

lock_registry = get_device_lock_registry()

device_options = {cd.alias: key for key, cd in connected.items()}
selected_aliases = st.multiselect(
    "Dispositivos a diagnosticar", list(device_options.keys()), default=list(device_options.keys())
)
selected_keys = [device_options[alias] for alias in selected_aliases]

st.divider()

results_store = st.session_state.setdefault(SESSION_DIAGNOSTIC_RESULTS, {})

if st.button(f"{ICONS['play']} Ejecutar diagnóstico", type="primary", disabled=not selected_keys):
    progress = st.progress(0.0, text="Iniciando diagnósticos...")
    total = len(selected_keys)
    for index, key in enumerate(selected_keys, start=1):
        device = connected[key]
        progress.progress((index - 1) / total, text=f"Diagnosticando {device.alias} ({index}/{total})...")

        with lock_registry.try_acquire(key) as acquired:
            if not acquired:
                st.warning(f"Ya hay un diagnóstico en curso para **{device.alias}**. Se omitió esta ejecución.")
                continue
            try:
                diagnostic = run_router_general_health(
                    device.connection, device_id=device.device_id, target_device_id=device.alias
                )
            except RouterAppError as exc:
                st.error(f"{device.alias}: {exc.friendly_message}")
                if exc.detail:
                    st.caption(f"Detalle técnico: {exc.detail}")
                continue
            except Exception:
                st.error(f"{device.alias}: ocurrió un error inesperado al ejecutar el diagnóstico.")
                continue
            results_store[key] = json.loads(diagnostic.model_dump_json())

    progress.progress(1.0, text="Diagnóstico completado.")

st.subheader(f"{ICONS['list']} Resultados")

if not results_store:
    st.info("Todavía no se ha ejecutado ningún diagnóstico en esta sesión.")
else:
    for key, diagnostic in results_store.items():
        device = connected.get(key)
        alias = device.alias if device is not None else diagnostic["target_device_id"]

        with st.expander(f"{ICONS['devices']} {alias} — {diagnostic['state']}", expanded=True):
            # Same state_badge() pill Historial uses, not st.success/warning/error's
            # built-in colors — those only have 4 visual treatments for the app's
            # 6 diagnostic states, which collapsed DEGRADED into WARNING and
            # UNREACHABLE into CRITICAL.
            st.markdown(
                f"**Estado general:** {state_badge(diagnostic['state'])}\n\n{diagnostic['summary']}",
                unsafe_allow_html=True,
            )

            col1, col2, col3 = st.columns(3)
            col1.metric(f"{ICONS['clock']} Duración (s)", diagnostic["duration_seconds"])
            col2.metric(f"{ICONS['calendar']} Inicio", format_datetime(diagnostic["started_at"]))
            col3.metric(f"{ICONS['check_wan']} Host", diagnostic["target_host"])

            if diagnostic.get("warnings"):
                for warning in diagnostic["warnings"]:
                    st.caption(f"{ICONS['warning']} {warning}")

            st.markdown(f"**{ICONS['success']} Chequeos**")
            rows = [
                {
                    "Chequeo": check["check_name"],
                    "Estado": check["state"],
                    "Valor": check["value"],
                    "Resumen": check["summary"],
                }
                for check in diagnostic["checks"]
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

            dl_col, ev_col, hist_col = st.columns(3)
            with dl_col:
                st.download_button(
                    f"{ICONS['download']} Descargar diagnóstico JSON",
                    data=json.dumps(diagnostic, ensure_ascii=False, indent=2),
                    file_name=f"{diagnostic['diagnostic_id']}.json",
                    mime="application/json",
                    key=f"download_diag_{diagnostic['diagnostic_id']}",
                )
            with ev_col:
                st.caption(f"{ICONS['link']} Ejecuciones relacionadas:")
                st.code("\n".join(diagnostic["evidence_execution_ids"]) or "(ninguna)")
            with hist_col:
                st.page_link("pages/3_Historial.py", label="Abrir historial", icon=ICONS["history"])
