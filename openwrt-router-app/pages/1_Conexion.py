from __future__ import annotations

import time
from datetime import datetime

import streamlit as st
import yaml

from core.constants import (
    CONNECTION_TEST_COMMAND,
    CONNECTION_TEST_MARKER,
    SESSION_ADHOC_DEVICE_KEY,
    SESSION_CONNECTED_DEVICES,
    SETTINGS_FILE,
)
from core.exceptions import RouterAppError
from core.formatting import format_datetime
from core.icons import ICONS
from core.ssh_client import SSHClient
from models.connection import ConnectionConfig, HostKeyPolicy
from models.device import ConnectedDevice, DeviceConfig
from repositories.device_repository import DeviceRepository


@st.cache_resource
def get_device_repository() -> DeviceRepository:
    return DeviceRepository()


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


def _connected_devices() -> dict[str, ConnectedDevice]:
    return st.session_state.setdefault(SESSION_CONNECTED_DEVICES, {})


def _to_device_config(record) -> DeviceConfig:
    return DeviceConfig(
        id=record.id,
        alias=record.alias,
        host=record.host,
        port=record.port,
        username=record.username,
        timeout=record.timeout,
        host_key_policy=HostKeyPolicy(record.host_key_policy),
        created_at=record.created_at,
    )


def _test_and_connect(key: str, device_id: int | None, alias: str, config: ConnectionConfig) -> None:
    started = time.monotonic()
    try:
        with st.spinner(f"Conectando con **{alias}** y validando…"):
            with SSHClient(config) as client:
                output = client.execute(CONNECTION_TEST_COMMAND, timeout=config.timeout)
        elapsed = time.monotonic() - started

        if CONNECTION_TEST_MARKER in output.stdout:
            _connected_devices()[key] = ConnectedDevice(
                key=key,
                device_id=device_id,
                alias=alias,
                connection=config,
                status="Conexión validada",
                connected_at=datetime.now().astimezone(),
            )
            st.success(f"Conexión exitosa con **{alias}**.")
            st.write(f"Host: `{config.host}` · Puerto: `{config.port}` · Usuario: `{config.username}`")
            st.write(f"Tiempo de conexión: {elapsed:.2f} s")
        else:
            st.error("La conexión se estableció, pero la respuesta del router no fue la esperada.")
    except RouterAppError as exc:
        st.error(exc.friendly_message)
        if exc.detail:
            st.caption(f"Detalle técnico: {exc.detail}")
    except Exception:
        st.error("Ocurrió un error inesperado al probar la conexión.")


st.title(f"{ICONS['connection']} Conexión al router")
st.write(
    "Administra el registro de gateways OpenWrt y las conexiones activas de esta sesión. "
    "La contraseña nunca se guarda en disco: solo vive en memoria mientras dure la sesión de Streamlit."
)

device_repository = get_device_repository()

tab_registry, tab_adhoc = st.tabs(
    [f"{ICONS['registry']} Dispositivos guardados", f"{ICONS['bolt']} Conexión rápida (sin guardar)"]
)

with tab_registry:
    st.subheader(f"{ICONS['registry']} Registro de gateways")
    devices = device_repository.list_all()

    if devices:
        st.dataframe(
            [
                {
                    "Alias": d.alias,
                    "Host": d.host,
                    "Puerto": d.port,
                    "Usuario": d.username,
                    "Política de host key": d.host_key_policy,
                }
                for d in devices
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Todavía no hay dispositivos guardados. Agrega uno abajo.")

    st.divider()
    st.subheader(f"{ICONS['add']} Agregar dispositivo")
    with st.form("add_device_form", clear_on_submit=True):
        new_alias = st.text_input("Alias")
        new_host = st.text_input("Dirección IP o hostname", value="192.168.1.1")
        new_port = st.number_input("Puerto SSH", min_value=1, max_value=65535, value=22, step=1)
        new_username = st.text_input("Usuario", value="root")
        new_timeout = st.number_input("Timeout (segundos)", min_value=1, max_value=120, value=10, step=1)
        add_submitted = st.form_submit_button("Agregar")

    if add_submitted:
        try:
            device = DeviceConfig(
                alias=new_alias,
                host=new_host,
                port=int(new_port),
                username=new_username,
                timeout=int(new_timeout),
                host_key_policy=_load_default_host_key_policy(),
            )
            device_repository.create(device)
        except RouterAppError as exc:
            st.error(exc.friendly_message)
        except Exception:
            st.error("Los datos del dispositivo no son válidos. Revisa alias, host y usuario.")
        else:
            st.success(f"Dispositivo **{new_alias}** agregado.")
            st.rerun()

    if devices:
        st.divider()
        st.subheader(f"{ICONS['settings']} Conectar / editar / eliminar")
        options = {f"{d.alias} ({d.host})": d for d in devices}
        selected_label = st.selectbox("Dispositivo", list(options.keys()), key="registry_device_select")
        selected_device = options[selected_label]

        connect_col, edit_col, delete_col = st.columns(3)

        with connect_col:
            st.markdown(f"**{ICONS['connect']} Conectar**")
            password = st.text_input(
                "Contraseña", type="password", key=f"password_input_{selected_device.id}"
            )
            if st.button("Probar conexión", key=f"connect_{selected_device.id}"):
                config = _to_device_config(selected_device).to_connection_config(password)
                _test_and_connect(str(selected_device.id), selected_device.id, selected_device.alias, config)

        with edit_col:
            st.markdown(f"**{ICONS['edit']} Editar**")
            with st.form(f"edit_device_form_{selected_device.id}"):
                edit_alias = st.text_input("Alias", value=selected_device.alias)
                edit_host = st.text_input("Host", value=selected_device.host)
                edit_port = st.number_input("Puerto", min_value=1, max_value=65535, value=selected_device.port, step=1)
                edit_username = st.text_input("Usuario", value=selected_device.username)
                edit_timeout = st.number_input(
                    "Timeout (s)", min_value=1, max_value=120, value=selected_device.timeout, step=1
                )
                edit_submitted = st.form_submit_button("Guardar cambios")
            if edit_submitted:
                try:
                    updated = DeviceConfig(
                        alias=edit_alias,
                        host=edit_host,
                        port=int(edit_port),
                        username=edit_username,
                        timeout=int(edit_timeout),
                        host_key_policy=HostKeyPolicy(selected_device.host_key_policy),
                    )
                    device_repository.update(selected_device.id, updated)
                except RouterAppError as exc:
                    st.error(exc.friendly_message)
                except Exception:
                    st.error("Los datos ingresados no son válidos.")
                else:
                    st.success("Dispositivo actualizado.")
                    st.rerun()

        with delete_col:
            st.markdown(f"**{ICONS['delete']} Eliminar**")
            confirm_delete = st.checkbox(
                f"Confirmo que deseo eliminar **{selected_device.alias}** del registro. Esta acción no se puede deshacer.",
                key=f"confirm_delete_{selected_device.id}",
            )
            if st.button("Eliminar dispositivo", disabled=not confirm_delete, key=f"delete_{selected_device.id}"):
                device_repository.delete(selected_device.id)
                _connected_devices().pop(str(selected_device.id), None)
                st.success("Dispositivo eliminado.")
                st.rerun()

with tab_adhoc:
    st.write(
        "Prueba una conexión puntual sin guardarla en el registro de dispositivos. "
        "Útil para una verificación rápida de un equipo que no vas a administrar de forma recurrente."
    )
    with st.form("adhoc_connection_form"):
        host = st.text_input("Dirección IP o hostname", value="192.168.1.1", key="adhoc_host")
        port = st.number_input("Puerto SSH", min_value=1, max_value=65535, value=22, step=1, key="adhoc_port")
        username = st.text_input("Usuario", value="root", key="adhoc_username")
        password = st.text_input("Contraseña", type="password", key="adhoc_password")
        timeout = st.number_input("Timeout (segundos)", min_value=1, max_value=120, value=10, step=1, key="adhoc_timeout")
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
            _test_and_connect(SESSION_ADHOC_DEVICE_KEY, None, f"{username}@{host}", config)

    if st.button(f"{ICONS['clear_all']} Limpiar conexión rápida"):
        _connected_devices().pop(SESSION_ADHOC_DEVICE_KEY, None)
        st.session_state.pop("adhoc_password", None)
        st.success("Se eliminó la conexión rápida de esta sesión.")
        st.rerun()

st.divider()
st.subheader(f"{ICONS['devices']} Dispositivos conectados en esta sesión")
connected = _connected_devices()

if not connected:
    st.info("No hay dispositivos conectados en esta sesión.")
else:
    st.dataframe(
        [
            {
                "Alias": cd.alias,
                "Host": cd.connection.host,
                "Usuario": cd.connection.username,
                "Estado": cd.status,
                "Conectado desde": format_datetime(cd.connected_at),
            }
            for cd in connected.values()
        ],
        use_container_width=True,
        hide_index=True,
    )

if st.button(f"{ICONS['clear_all']} Limpiar todas las conexiones"):
    st.session_state[SESSION_CONNECTED_DEVICES] = {}
    st.success("Se eliminaron todas las conexiones activas de esta sesión.")
    st.rerun()
