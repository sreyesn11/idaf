# OpenWrt Router Diagnostic App

Mini aplicación web local para administrar, consultar y diagnosticar un
router OpenWrt mediante conexión SSH. Es el primer módulo (nombre interno
`openwrt-router-app`) de una arquitectura de observabilidad y diagnóstico
automático para redes IoT desarrollada como parte de una tesis de maestría.
En esta primera fase el alcance está limitado exclusivamente al router
OpenWrt: no se implementan todavía ESP32, Thread/OpenThread, MQTT,
Prometheus, Grafana ni ThingsBoard, aunque la arquitectura queda preparada
para integrarlos en fases posteriores.

Versión actual: **v0.2.0 — Primer diagnóstico general del router OpenWrt**.

## 1. Descripción

La aplicación permite configurar una conexión SSH a un router OpenWrt,
probar la conectividad, ejecutar comandos de diagnóstico predefinidos
(nunca comandos libres), capturar y estructurar la salida, mostrarla en una
interfaz Streamlit, y guardar tanto un historial en SQLite como evidencias
en archivos JSON. Además de ejecutar comandos individuales, incluye un
diagnóstico consolidado llamado **Router General Health**, que ejecuta
varias consultas seguras, normaliza sus métricas, aplica reglas de umbral y
devuelve un estado general (`HEALTHY`, `WARNING`, `DEGRADED`, `CRITICAL`,
`UNREACHABLE` o `UNKNOWN`).

## 2. Requisitos

- Python 3.11 o superior.
- Acceso SSH a un router OpenWrt (o a un entorno de laboratorio que lo simule).

## 3. Instalación

Clona este repositorio y sitúate dentro de la carpeta de la aplicación:

```bash
cd openwrt-router-app
```

Todos los comandos de las secciones siguientes (entorno virtual, dependencias,
ejecución, pruebas) se ejecutan desde dentro de `openwrt-router-app/`.

## 4. Creación de entorno virtual

```bash
python -m venv venv
```

Activación en Windows:

```bash
venv\Scripts\activate
```

Activación en Linux/macOS:

```bash
source venv/bin/activate
```

## 5. Instalación de dependencias

```bash
pip install -r requirements.txt
```

## 6. Ejecución

```bash
streamlit run app.py
```

La aplicación abrirá en el navegador con 5 secciones accesibles desde el
menú lateral: Inicio, Conexión, Comandos, Historial, Diagnóstico y Acerca de.

## 7. Estructura

```text
openwrt-router-app/
├── app.py                          # Página de Inicio (Streamlit)
├── pages/
│   ├── 1_Conexion.py               # Configuración, prueba y limpieza de conexión SSH
│   ├── 2_Comandos.py               # Selección/ejecución de comandos y resultado
│   ├── 3_Historial.py              # Historial: pestañas Ejecuciones / Diagnósticos
│   ├── 4_Diagnostico.py            # Diagnóstico general del router (Router General Health)
│   └── 5_Acerca_de.py
├── core/
│   ├── ssh_client.py               # Conexión y ejecución SSH (Paramiko)
│   ├── command_service.py          # Carga y valida config/commands.yaml
│   ├── execution_service.py        # Orquesta SSH -> parser -> BD -> evidencia
│   ├── logging_config.py           # Logging rotativo a logs/app.log
│   ├── exceptions.py                # Jerarquía de excepciones propias
│   └── constants.py
├── diagnostics/
│   ├── enums.py                     # DiagnosticState
│   ├── models.py                    # DiagnosticCheckResult, RouterDiagnosticResult
│   ├── thresholds.py                # Carga config/diagnostic_thresholds.yaml
│   ├── rules.py                     # Una regla por chequeo (SSH, memoria, LAN, WAN, ...)
│   ├── consolidator.py              # Consolida el estado general del diagnóstico
│   └── router_health_service.py     # Orquesta el diagnóstico completo
├── workflows/
│   └── router_general_health.py     # Punto de entrada del workflow "Router General Health"
├── models/                          # Modelos Pydantic (connection, command, execution)
├── parsers/                         # Un parser por formato de salida
├── repositories/                    # Persistencia en SQLite (SQLAlchemy)
│   ├── execution_repository.py      # Tabla `executions`
│   └── diagnostic_repository.py     # Tabla `diagnostics` (independiente de `executions`)
├── config/
│   ├── commands.yaml                # Lista blanca de comandos permitidos
│   ├── settings.yaml                # Política de host key SSH
│   └── diagnostic_thresholds.yaml   # Umbrales del diagnóstico Router General Health
├── evidence/
│   ├── executions/YYYY/MM/DD/<execution_id>.json
│   └── diagnostics/YYYY/MM/DD/<diagnostic_id>.json
├── logs/                            # logs/app.log (rotativo)
├── tests/                           # Pruebas unitarias (pytest, sin SSH real)
├── requirements.txt
└── pyproject.toml
```

## 8. Configuración

### 8.1 Comandos permitidos (`config/commands.yaml`)

Cada comando declara `id`, `name`, `description`, `command`, `parser`
(`json`, `text`, `lines`, `uptime`, `free` o `df`), `category`, `timeout` y
`enabled`. Solo se cargan y muestran los comandos con `enabled: true`. No
existe ningún campo de comando libre en la interfaz. El archivo se valida al
cargarlo: se detectan archivo inexistente, IDs duplicados, `parser`
inválido, `timeout` inválido y el caso de cero comandos habilitados,
lanzando `CommandConfigurationError` con un mensaje amigable en la interfaz.

### 8.2 Política de clave de host SSH (`config/settings.yaml`)

```yaml
ssh:
  host_key_policy: auto   # auto | reject
```

`auto` acepta automáticamente claves de host desconocidas (`AutoAddPolicy`)
y solo debe usarse en un laboratorio controlado. `reject` rechaza cualquier
clave de host no registrada previamente.

### 8.3 Umbrales de diagnóstico (`config/diagnostic_thresholds.yaml`)

Define los umbrales usados por el diagnóstico `router_general_health`:
latencia SSH, porcentaje de memoria, porcentaje de almacenamiento, carga
relativa por núcleo, segundos mínimos de uptime, y si WAN/IPv6/Wi-Fi son
obligatorias (`required: true|false`). Por defecto WAN, IPv6 y Wi-Fi no son
obligatorias, ya que el laboratorio puede operar sin ellas en esta fase.

## 9. Uso

1. En **Conexión**, ingresa host, puerto, usuario, contraseña y timeout, y
   presiona "Probar conexión". La contraseña solo vive en memoria durante
   la sesión de Streamlit; el botón "Limpiar credenciales" la borra junto
   con la conexión activa.
2. En **Comandos**, filtra por categoría, selecciona un comando de la lista
   blanca y presiona "Ejecutar". El resultado (estado, código de salida,
   duración, stdout, stderr, datos estructurados) se muestra debajo, junto
   con un botón para descargar la evidencia JSON.
3. En **Diagnóstico**, presiona "Ejecutar diagnóstico" para correr
   automáticamente el diagnóstico Router General Health: valida SSH y
   evalúa identidad, uptime/carga, memoria, almacenamiento, LAN, WAN, IPv6
   y Wi-Fi. Muestra el estado general, el detalle por chequeo y permite
   descargar la evidencia JSON.
4. En **Historial**, la pestaña "Ejecuciones" filtra por estado/categoría o
   busca por comando; la pestaña "Diagnósticos" filtra por estado o busca
   por host/resumen. Ambas permiten abrir el detalle, descargar evidencia,
   eliminar registros individuales o limpiar todo el historial (con
   confirmación).

## 10. Seguridad

- Solo se permiten comandos predefinidos en `config/commands.yaml`; no hay
  entrada de comandos libres ni concatenación de comandos con datos del
  usuario, y no se usa `shell=True`.
- La aplicación no modifica la configuración del router ni ejecuta comandos
  destructivos.
- La contraseña SSH nunca se guarda en SQLite, JSON, YAML, logs ni ningún
  otro almacenamiento persistente; solo permanece en `st.session_state`
  durante la sesión activa de Streamlit, y puede borrarse manualmente con
  el botón "Limpiar credenciales".
- Los logs (`logs/app.log`) registran host, usuario, id de comando,
  duración y estado, pero nunca contraseñas ni credenciales.
- Los errores se traducen siempre a un mensaje amigable; nunca se muestra
  un stack trace completo ni el texto crudo de una excepción no controlada
  al usuario final.
- Si falla la escritura de evidencia o la persistencia en SQLite, el
  resultado ya calculado (de una ejecución o de un diagnóstico) igual se
  muestra en la interfaz; el fallo solo se registra en el log.

## 11. Pruebas

```bash
pytest -v
```

Las pruebas cubren carga y validación de `commands.yaml` (incluyendo los
casos de error de la sección 8.1), cada parser, los modelos Pydantic, el
flujo de `ExecutionService`, las reglas de diagnóstico (`diagnostics/rules.py`),
el consolidador de estado (`diagnostics/consolidator.py`), el
`RouterHealthService` (con mocks: éxito, SSH inalcanzable, comando no
disponible, fallo de parsing, fallo de persistencia y fallo de escritura de
evidencia) y el `DiagnosticRepository`. Ninguna prueba abre una conexión SSH
real: `SSHClient` se sustituye por un doble de prueba.

## 12. Limitaciones

- Primera fase limitada al router OpenWrt: no incluye ESP32, Thread/
  OpenThread, MQTT, Prometheus, Grafana, ThingsBoard, health score,
  machine learning, remediación automática ni múltiples routers.
- No todos los comandos de `commands.yaml` están garantizados en todas las
  versiones/variantes de OpenWrt (por ejemplo, `iwinfo` o `ubus` pueden no
  estar disponibles según la imagen instalada); en ese caso la ejecución
  queda registrada como `FAILED` y el chequeo correspondiente se marca
  `UNKNOWN` en el diagnóstico.
- Los parsers de `uptime`, `free` y `df`, y las reglas que dependen de ellos
  (uptime/carga, memoria, almacenamiento), son de mejor esfuerzo (BusyBox
  varía su formato de salida); si no logran interpretar la salida, el
  chequeo correspondiente se marca `UNKNOWN` conservando el stdout crudo.
- El diagnóstico no calcula un "health score" ni promedio: el estado
  general se decide con una jerarquía de reglas fija (sección 9 del
  documento de diseño), no con machine learning ni remediación automática.

## 13. Próximos pasos

Integración, en fases posteriores, con nodos ESP32, Thread/OpenThread,
MQTT, Prometheus, Grafana y ThingsBoard, dentro de la arquitectura general
de observabilidad de la tesis.
