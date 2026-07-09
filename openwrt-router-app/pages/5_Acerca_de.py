from __future__ import annotations

import streamlit as st

from core.constants import APP_INTERNAL_NAME, APP_NAME, APP_VERSION

st.set_page_config(page_title=f"Acerca de — {APP_NAME}", page_icon="ℹ️", layout="wide")

st.title("Acerca de")

st.write(f"**{APP_NAME}** (`{APP_INTERNAL_NAME}`) — versión {APP_VERSION}")

st.markdown(
    """
Esta aplicación es el primer módulo de una arquitectura de observabilidad y
diagnóstico automático para redes IoT, desarrollada como parte de una tesis
de maestría.

En esta primera fase, el alcance está limitado exclusivamente al diagnóstico
y administración de un router OpenWrt mediante SSH. La aplicación está
preparada arquitectónicamente para integrar en fases posteriores:

- Nodos ESP32.
- Thread / OpenThread.
- MQTT.
- Prometheus y Grafana.
- ThingsBoard.

Estos componentes **no** están implementados todavía.
"""
)

st.subheader("Alcance de seguridad")
st.markdown(
    """
- No se modifica la configuración del router.
- Solo se permiten comandos predefinidos y habilitados en `config/commands.yaml`.
- La contraseña SSH nunca se almacena en disco ni se registra en los logs.
- No se muestran errores técnicos completos al usuario final.
"""
)
