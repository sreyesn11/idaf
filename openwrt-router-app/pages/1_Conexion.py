from __future__ import annotations

import time

import streamlit as st
import yaml

from core.constants import (
    APP_NAME,
    CONNECTION_TEST_COMMAND,
    CONNECTION_TEST_MARKER,
    SESSION_CONNECTION_CONFIG,
    SESSION_CONNECTION_STATUS,
    SETTINGS_FILE,
)
from core.exceptions import RouterAppError
from core.ssh_client import SSHClient
from models.connection import ConnectionConfig, HostKeyPolicy

st.set_page_config(page_title=f"Conexión — {APP_NAME}", page_icon="🔌", layout="wide")


def _load_default_host_key_policy() -> HostKeyPolicy:
    if not SETTINGS_FILE.exists():
        return HostKeyPolicy.AUTO
    with SETTINGS_FILE.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    value = (raw.get("ssh") or {}).get("host_key_policy", "auto")
    try:
        return HostKeyPolicy(value)
    except ValueError:
        return HostKeyPolicy.AUTO


st.title("Conexión al router")
st.write(
    "Configura los datos de conexión SSH. La contraseña solo se conserva en memoria "
    "durante esta sesión de Streamlit; nunca se guarda en disco ni en el historial."
)

with st.form("connection_form"):
    host = st.text_input("Dirección IP o hostname", value="192.168.1.1")
    port = st.number_input("Puerto SSH", min_value=1, max_value=65535, value=22, step=1)
    username = st.text_input("Usuario", value="root")
    password = st.text_input("Contraseña", type="password")
    timeout = st.number_input("Timeout (segundos)", min_value=1, max_value=120, value=10, step=1)
    submitted = st.form_submit_button("Probar conexión")

if submitted:
    try:
        config = ConnectionConfig(
            host=host,
            port=int(port),
            username=username,
            password=password,
            timeout=int(timeout),
            host_key_policy=_load_default_host_key_policy(),
        )
    except Exception:
        st.error("Los datos de conexión ingresados no son válidos. Revisa host y usuario.")
    else:
        started = time.monotonic()
        try:
            with SSHClient(config) as client:
                output = client.execute(CONNECTION_TEST_COMMAND, timeout=config.timeout)
            elapsed = time.monotonic() - started

            if CONNECTION_TEST_MARKER in output.stdout:
                st.session_state[SESSION_CONNECTION_CONFIG] = config
                st.session_state[SESSION_CONNECTION_STATUS] = "Conectado"
                st.success("Conexión exitosa.")
                st.write(f"Host: `{config.host}` · Puerto: `{config.port}` · Usuario: `{config.username}`")
                st.write(f"Tiempo de conexión: {elapsed:.2f} s")
            else:
                st.session_state[SESSION_CONNECTION_STATUS] = "Fallida"
                st.error("La conexión se estableció, pero la respuesta del router no fue la esperada.")
        except RouterAppError as exc:
            st.session_state[SESSION_CONNECTION_STATUS] = "Fallida"
            st.error(exc.friendly_message)
            if exc.detail:
                st.caption(f"Detalle técnico: {exc.detail}")
        except Exception:
            st.session_state[SESSION_CONNECTION_STATUS] = "Fallida"
            st.error("Ocurrió un error inesperado al probar la conexión.")

current_config: ConnectionConfig | None = st.session_state.get(SESSION_CONNECTION_CONFIG)
if current_config is not None:
    st.divider()
    st.caption(
        f"Conexión activa en esta sesión: {current_config.username}@{current_config.host}:{current_config.port}"
    )
