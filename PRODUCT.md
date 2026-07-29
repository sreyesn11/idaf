# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Streamlit (Python 3.11+) server-rendered UI, Paramiko SSH, Pydantic models, SQLAlchemy + SQLite history, PyYAML config. No React/Node/Django/Flask — this is a Python-only multipage Streamlit app (`openwrt-router-app/`), not a hand-authored HTML/CSS/JSX frontend. Existing codebase; not a stack decision to make.

## Users

Un solo operador (el propio maestrante) usando la app desde su equipo de desarrollo en un laboratorio interno, no un producto multiusuario ni de cara al público. La tarea: administrar el registro de routers OpenWrt del laboratorio, ejecutar comandos de diagnóstico predefinidos por SSH, correr el diagnóstico consolidado "Router General Health" y revisar el historial/eventos resultantes.

## Product Purpose

Primer módulo (MVP) de una arquitectura de observabilidad y diagnóstico para redes IoT, desarrollada como parte de una tesis de maestría (IDAF, Universidad Nacional de Colombia). En esta fase el alcance está limitado exclusivamente a: conexión SSH a un router OpenWrt, ejecución de comandos de una lista blanca, parsing de la salida, un diagnóstico consolidado de salud del router, e historial/evidencia persistidos en SQLite + JSON.

## Positioning

No es una herramienta comercial de monitoreo de red (no compite con Grafana/Zabbix/etc.). Es la capa base, deliberadamente mínima y auditable, de una arquitectura académica que dejará espacio arquitectónico —pero no implementación— para ESP32, Thread/OpenThread, MQTT, Prometheus, Grafana y ThingsBoard en fases posteriores.

## Operating Context

Uso desde un navegador de escritorio mientras se corre `streamlit run app.py` localmente contra uno o varios routers OpenWrt de laboratorio, generalmente en la misma LAN. Sesiones cortas, un operador técnico a la vez. Las páginas (`app.py` + `pages/1_Conexion.py` … `6_Acerca_de.py`) representan flujos secuenciales: conectar → ejecutar comando o diagnóstico → revisar historial/topología.

## Capabilities and Constraints

- Solo comandos de una lista blanca (`config/commands.yaml`); no hay campo de comando libre en la UI.
- Las contraseñas SSH nunca se persisten (ni SQLite, ni JSON, ni logs); solo viven en `st.session_state` durante la sesión.
- El diagnóstico nunca calcula un "health score" numérico: el estado general sale de una jerarquía de reglas fija (`diagnostics/consolidator.py`), no de un promedio ni de ML.
- Los diagnósticos contra distintos dispositivos siempre corren secuencialmente, nunca en paralelo sobre el mismo router (`core/concurrency.py`).
- No todos los comandos/herramientas de OpenWrt (p. ej. `iwinfo`, `ubus`) están garantizados en todo dispositivo/versión: una ejecución faltante degrada a `FAILED`/`UNKNOWN`, nunca revienta la app.
- Todo texto de UI, logs y mensajes de error está en español.

## Brand Commitments

Logo institucional de la Universidad Nacional de Colombia (`assets/logo_unal.png`) en la barra lateral de cada página. Color primario ya establecido: verde institucional `#94b43b` (variante oscura `#6f872c`), definido en `core/branding.py` y en el tema de Streamlit (`.streamlit/config.toml`). Un solo set de iconos (Material Symbols vía shortcodes de Streamlit, `core/icons.py`) — no emoji ni mezclas de estilos de ícono.

## Evidence on Hand

Specs fuente de verdad ya existentes en el repo: `Prompt_Claude_Mini_App_OpenWrt.md` (spec del MVP) e `IDAF_MVP_Primer_Diagnostico_OpenWrt.md` (spec del diagnóstico Router General Health). `README.md` documenta arquitectura y capas. No hay testimonios, casos de estudio ni activos de marketing — no aplica para este producto interno de laboratorio.

## Product Principles

1. Nunca sacrificar las reglas no negociables (lista blanca de comandos, cero contraseñas persistidas, capas separadas, textos en español) por una mejora visual.
2. El estado de salud del router (HEALTHY/WARNING/DEGRADED/CRITICAL/UNREACHABLE/UNKNOWN) es la señal más importante de la interfaz: debe ser legible al primer vistazo y con contraste correcto en todos lados donde aparece (badges, métricas, topología).
3. Es una herramienta "Operate" (tarea, no persuasión): densidad de información, escaneabilidad y consistencia priman sobre expresividad visual.
4. Un solo lenguaje visual para conceptos repetidos (colores de estado, iconografía, tarjetas de métricas) en vez de que cada página reinvente su propio estilo.

## Accessibility & Inclusion

Sin requisito de accesibilidad formal declarado por el usuario, pero como buena práctica del laboratorio: los indicadores de estado por color deben mantener contraste texto/fondo ≥ 4.5:1 (WCAG AA) y no depender solo del color para transmitir significado (siempre acompañado de texto/etiqueta, nunca solo un punto de color).
