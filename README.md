# OpenWrt Router Diagnostic App

Mini aplicación web local para administrar, consultar y diagnosticar un
router OpenWrt mediante conexión SSH. Es el primer módulo (nombre interno
`openwrt-router-app`) de una arquitectura de observabilidad y diagnóstico
automático para redes IoT desarrollada como parte de una tesis de maestría.
En esta primera fase el alcance está limitado exclusivamente al router
OpenWrt: no se implementan todavía ESP32, Thread/OpenThread, MQTT,
Prometheus, Grafana ni ThingsBoard, aunque la arquitectura queda preparada
para integrarlos en fases posteriores.

Versión actual: **v0.3.0-dev — Descubrimiento automático (simulado) e inventario de dispositivos**.

## 1. Descripción

La aplicación permite configurar una conexión SSH a uno o varios routers
OpenWrt, probar la conectividad, ejecutar comandos de diagnóstico
predefinidos (nunca comandos libres), capturar y estructurar la salida,
mostrarla en una interfaz Streamlit, y guardar tanto un historial en SQLite
como evidencias en archivos JSON. Incluye un diagnóstico consolidado
llamado **Router General Health**, que ejecuta varias consultas seguras,
normaliza sus métricas, aplica reglas de umbral y devuelve un estado
general (`HEALTHY`, `WARNING`, `DEGRADED`, `CRITICAL`, `UNREACHABLE` o
`UNKNOWN`).

Desde v0.3.0-dev, además, incorpora un módulo de **descubrimiento e
inventario de dispositivos** (sección 9 más abajo): un pipeline de
colección → normalización → resolución de identidad → aprobación manual →
inventario/topología, funcionando por ahora completamente sobre datos
**simulados** (fixtures JSON), sin ningún escaneo o conexión de red real —
ver `docs/discovery_architecture.md` para el detalle completo.

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

La aplicación abrirá en el navegador con 7 secciones accesibles desde el
menú lateral (además de Inicio): Conexión, Comandos, Historial, Diagnóstico,
Topología, Descubrimiento y Acerca de.

## 7. Estructura

```text
openwrt-router-app/
├── app.py                          # Página de Inicio (Streamlit)
├── pages/
│   ├── 1_Conexion.py               # Registro de dispositivos, conexión/desconexión por sesión
│   ├── 2_Comandos.py               # Selección/ejecución de comandos y resultado
│   ├── 3_Historial.py              # Historial: pestañas Ejecuciones / Diagnósticos / Eventos
│   ├── 4_Diagnostico.py            # Diagnóstico general (Router General Health), uno o varios dispositivos
│   ├── 5_Topologia.py              # Topología PC -> OpenWrt + árbol de inventario descubierto
│   ├── 7_Descubrimiento.py         # Descubrimiento simulado, pendientes, inventario, conflictos, registro manual
│   └── 6_Acerca_de.py
├── core/
│   ├── ssh_client.py               # Conexión y ejecución SSH (Paramiko)
│   ├── command_service.py          # Carga y valida config/commands.yaml
│   ├── execution_service.py        # Orquesta SSH -> parser -> BD -> evidencia
│   ├── concurrency.py              # Bloqueo por dispositivo (evita diagnósticos simultáneos sobre el mismo router)
│   ├── logging_config.py           # Logging rotativo a logs/app.log
│   ├── exceptions.py                # Jerarquía de excepciones propias
│   ├── branding.py                  # Fuente única de colores de estado, radios y CSS global (ver sección 14)
│   ├── icons.py                     # Íconos de línea monocromos usados en la UI
│   ├── formatting.py                # Formateo de fechas/valores para la UI
│   └── constants.py
├── diagnostics/
│   ├── enums.py                     # DiagnosticState
│   ├── models.py                    # DiagnosticCheckResult, RouterDiagnosticResult
│   ├── thresholds.py                # Carga config/diagnostic_thresholds.yaml
│   ├── rules.py                     # Una regla por chequeo (SSH, memoria, LAN, WAN, ...)
│   ├── consolidator.py              # Consolida el estado general del diagnóstico
│   └── router_health_service.py     # Orquesta el diagnóstico completo y detecta cambios de estado
├── events/
│   ├── models.py                    # StateChangeEvent
│   └── event_repository.py          # Tabla `events`
├── topology/
│   ├── models.py                    # TopologyNode, TopologyLink, TopologyGraph
│   ├── builder.py                   # Topología PC -> OpenWrt y build_inventory_topology() (descubrimiento)
│   └── renderer.py                  # Diagrama animado PC<->router + árbol de inventario (sin dependencias nuevas)
├── workflows/
│   └── router_general_health.py     # Punto de entrada del workflow "Router General Health"
├── discovery/                       # Descubrimiento e inventario (ver docs/discovery_architecture.md)
│   ├── enums.py                     # DeviceDiscoveryStatus, IdentifierType, CorrelationStatus, ...
│   ├── models.py                    # RawDiscoveryObservation, NormalizedObservation, IdentityResolution, ...
│   ├── collectors/                  # DiscoveryCollector (Protocol), SimulatedDiscoveryCollector, fixtures/
│   ├── normalization/               # validators.py + normalizer.py
│   ├── correlation/                 # identity_resolver.py, duplicate_detector.py, merge_planner.py
│   ├── services/                    # discovery_service.py, onboarding_service.py, inventory_service.py
│   └── repositories/                # inventory_device, identifier, address, interface, observation, topology_link
├── models/                          # Modelos Pydantic (connection, command, execution, device)
├── parsers/                         # Un parser por formato de salida
├── repositories/                    # Persistencia en SQLite (SQLAlchemy)
│   ├── execution_repository.py      # Tabla `executions`
│   ├── diagnostic_repository.py     # Tabla `diagnostics` (independiente de `executions`)
│   └── device_repository.py         # Tabla `devices` (registro de gateways, sin contraseña)
├── config/
│   ├── commands.yaml                # Lista blanca de comandos permitidos
│   ├── settings.yaml                # Política de host key SSH
│   └── diagnostic_thresholds.yaml   # Umbrales del diagnóstico Router General Health
├── evidence/
│   ├── executions/YYYY/MM/DD/<execution_id>.json
│   ├── diagnostics/YYYY/MM/DD/<diagnostic_id>.json
│   └── discovery/YYYY/MM/DD/<execution_id>.json
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

### 8.4 Validación manual en el router

Si el diagnóstico marca un chequeo como `UNKNOWN` o `FAILED`, estos son los
mismos comandos que usa la app y que puedes correr directamente por SSH en el
router para investigar la causa:

```bash
ubus call system board                       # identidad: hostname, modelo, kernel, release
uptime                                       # uptime y load average
free                                         # memoria usada/disponible
df -h                                        # uso de almacenamiento por filesystem
ubus call network.interface.lan status       # estado de la interfaz LAN
ubus call network.interface.wan status       # estado de la interfaz WAN
ip -6 addr show                              # direcciones IPv6 configuradas
ubus call network.wireless status            # estado de las radios Wi-Fi
/etc/init.d/dropbear status                  # estado del servidor SSH (dropbear)
date                                         # hora/fecha del sistema, útil para correlacionar con evidencias
```

Recomendaciones de configuración del router para este laboratorio:

- Hostname sugerido: `idaf-openwrt`.
- Zona horaria sugerida: `America/Bogota`.
- **Nunca** expongas el servicio SSH (dropbear) en la interfaz WAN; la
  administración y el diagnóstico deben hacerse siempre desde la LAN.

## 9. Descubrimiento e inventario (v0.3.0-dev)

Módulo nuevo, sección de navegación **Descubrimiento**. Todo corre sobre
datos **simulados** (fixtures JSON) — no hay escaneo ni conexión de red
real todavía (ver `docs/simulated_discovery.md` y
`docs/future_real_collectors.md`).

Flujo: colector simulado → normalización → resolución de identidad → el
dispositivo queda `PENDING_APPROVAL` → aprobación/edición/ignorar/fusión
manual → inventario y topología. Un dispositivo descubierto **nunca** pasa
a administrado automáticamente, y una coincidencia de IP sola **nunca**
fusiona dos dispositivos (ver `docs/device_identity.md` para el algoritmo
completo de resolución de identidad y sus umbrales de confianza).

Pestañas de la página:

- **Resumen**: conteos por estado, observaciones totales, conflictos de
  identidad, posibles duplicados, y un botón para marcar como `STALE` los
  dispositivos sin observar recientemente.
- **Ejecutar descubrimiento**: elige un fixture de
  `discovery/collectors/fixtures/`, lo corre, y muestra el resultado por
  observación más la evidencia JSON descargable.
- **Pendientes**: dispositivos recién descubiertos — aprobar tal cual,
  editar y aprobar, o ignorar.
- **Inventario**: todos los dispositivos, filtrables por estado.
- **Ignorados**: permite restaurar un dispositivo ignorado.
- **Conflictos y duplicados**: observaciones marcadas `IDENTITY_CONFLICT`
  y pares de dispositivos que comparten un identificador, con fusión
  manual confirmada (transaccional, con reversión si algo falla).
- **Registro manual**: da de alta un dispositivo directamente como
  `APPROVED`, sin pasar por el flujo de descubrimiento.

La pestaña **Topología** (sección 5 de la estructura) se extendió con un
árbol de inventario (dispositivos aprobados/pendientes y sus enlaces
padre-hijo detectados), independiente del diagrama PC↔router existente.

## 10. Uso

1. En **Conexión**, en la pestaña "Dispositivos guardados" registra uno o
   varios gateways (alias, host, puerto, usuario — sin contraseña) y
   presiona "Probar conexión" para cada uno con su contraseña de sesión; la
   pestaña "Conexión rápida" permite una conexión puntual sin guardar. La
   contraseña nunca se guarda en disco, solo vive en memoria durante la
   sesión de Streamlit; "Limpiar todas las conexiones" borra todas las
   conexiones activas de la sesión.
2. En **Comandos**, elige el dispositivo activo entre los conectados, filtra
   por categoría, selecciona un comando de la lista blanca y presiona
   "Ejecutar". El resultado (estado, código de salida, duración, stdout,
   stderr, datos estructurados) se muestra debajo, junto con un botón para
   descargar la evidencia JSON.
3. En **Diagnóstico**, selecciona uno o varios dispositivos conectados y
   presiona "Ejecutar diagnóstico" para correr el diagnóstico Router General
   Health sobre cada uno, en orden (nunca en paralelo sobre el mismo
   dispositivo, para no saturarlo): valida SSH y evalúa identidad,
   uptime/carga, memoria, almacenamiento, LAN, WAN, IPv6 y Wi-Fi. Cada
   dispositivo muestra su propio estado general, detalle por chequeo y
   evidencia JSON descargable, sin combinarse en una vista comparativa.
4. En **Historial**, la pestaña "Ejecuciones" filtra por estado/categoría/
   dispositivo o busca por comando; la pestaña "Diagnósticos" filtra por
   estado/dispositivo o busca por host/resumen; la pestaña "Eventos" lista
   los cambios de estado detectados entre diagnósticos consecutivos de un
   mismo dispositivo (fecha, tipo, dispositivo, estado anterior, estado
   nuevo, fuente). Las tres permiten limpiar su historial (con
   confirmación); Ejecuciones y Diagnósticos también permiten abrir el
   detalle, descargar evidencia y eliminar registros individuales.
5. En **Topología**, elige un dispositivo guardado para ver la topología
   mínima `PC Desarrollo -> OpenWrt`, coloreada según el estado de su último
   diagnóstico (o `UNKNOWN` si todavía no se ha ejecutado ninguno).

## 11. Seguridad

- Solo se permiten comandos predefinidos en `config/commands.yaml`; no hay
  entrada de comandos libres ni concatenación de comandos con datos del
  usuario, y no se usa `shell=True`.
- La aplicación no modifica la configuración del router ni ejecuta comandos
  destructivos.
- La contraseña SSH nunca se guarda en SQLite, JSON, YAML, logs ni ningún
  otro almacenamiento persistente; solo permanece en `st.session_state`
  durante la sesión activa de Streamlit, y puede borrarse manualmente
  desconectando el dispositivo o con "Limpiar todas las conexiones".
- Los logs (`logs/app.log`) registran host, usuario, id de comando,
  duración y estado, pero nunca contraseñas ni credenciales.
- Los errores se traducen siempre a un mensaje amigable; nunca se muestra
  un stack trace completo ni el texto crudo de una excepción no controlada
  al usuario final.
- Si falla la escritura de evidencia o la persistencia en SQLite, el
  resultado ya calculado (de una ejecución o de un diagnóstico) igual se
  muestra en la interfaz; el fallo solo se registra en el log.

## 12. Pruebas

```bash
pytest -v
```

Las pruebas cubren carga y validación de `commands.yaml` (incluyendo los
casos de error de la sección 8.1), cada parser, los modelos Pydantic, el
flujo de `ExecutionService` y `ExecutionRepository`, las reglas de
diagnóstico (`diagnostics/rules.py`), el consolidador de estado
(`diagnostics/consolidator.py`), el `RouterHealthService` (con mocks: éxito,
SSH inalcanzable, comando no disponible, fallo de parsing, fallo de
persistencia, fallo de escritura de evidencia, y detección/no-detección de
cambio de estado), el `DiagnosticRepository` (incluyendo
`get_latest_for_target`), el registro de dispositivos (`DeviceRepository`,
sin columna de contraseña), la migración idempotente de columnas
(`repositories/database.py`), el bloqueo por dispositivo
(`core/concurrency.py`), los eventos de cambio de estado (`EventRepository`)
y el constructor de topología (`topology/builder.py`). Ninguna prueba abre
una conexión SSH real: `SSHClient` se sustituye por un doble de prueba.

El módulo de descubrimiento agrega su propia suite (61 pruebas, sin red
real): normalización (MAC/IPv4/IPv6/hostname/Thread/timestamps válidos e
inválidos), resolución de identidad (todos los casos de la sección 8.3 de
la spec: coincidencia fuerte/media/débil, conflicto, dispositivo manual
detectado después), persistencia (identificadores, direcciones IPv4/IPv6,
fusión transaccional con prueba de reversión ante fallo), el flujo completo
de `DiscoveryService` contra el fixture simulado (incluyendo idempotencia
al correrlo dos veces), el flujo de aprobación/ignorar/restaurar/fusionar,
y `build_inventory_topology()` (dispositivos ignorados nunca aparecen,
enlaces requieren ambos extremos visibles).

## 13. Diseño

El proyecto usa el skill [Impeccable](https://impeccable.style/) (instalado
en `.claude/skills/impeccable/`) para el trabajo de diseño de la interfaz
Streamlit. `PRODUCT.md` y `DESIGN.md`, en la raíz del repo, documentan el
contexto de producto y las decisiones visuales vigentes (paleta, tipografía,
radios, tono) y sí se versionan en git aunque el resto de archivos `.md`
esté excluido (ver `.gitignore`).

Los colores de estado del diagnóstico (`HEALTHY/WARNING/DEGRADED/CRITICAL/
UNREACHABLE/UNKNOWN`) viven en un único lugar, `core/branding.py`
(`STATE_COLORS`, `STATE_TEXT_ON_LIGHT_COLORS`, `TEXT_COLOR`); tanto
`state_badge()` como `topology/renderer.py` importan de ahí en vez de
mantener copias duplicadas de la paleta. El texto sobre los colores de
estado es siempre oscuro (`#1b1b1b`), no blanco, para cumplir contraste
WCAG AA (≥4.5:1) en los cinco estados.

## 14. Limitaciones

- Primera fase limitada al router OpenWrt: no incluye ESP32, Thread/
  OpenThread, MQTT, Prometheus, Grafana, ThingsBoard, health score,
  machine learning ni remediación automática. Sí soporta administrar y
  diagnosticar varios routers OpenWrt (registro de dispositivos), ejecutando
  los diagnósticos de forma secuencial para no saturar ningún equipo.
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
- El descubrimiento de dispositivos (sección 9) es completamente
  **simulado**: no hay VPN, acceso SSH confirmado al Linksys, ni
  confirmación de qué herramientas de descubrimiento soporta su firmware
  (ver `docs/simulated_discovery.md` y `docs/future_real_collectors.md`).
  No implementa Thread/OpenThread, MQTT, Prometheus, Grafana ni
  ThingsBoard — el tipo de observación `THREAD_NODE_REPORT` existe solo
  para validar que el modelo de datos ya los soporta.

## 15. Próximos pasos

Integración, en fases posteriores, con un colector de descubrimiento real
(empezando por reportes de gateway vía SSH — ver
`docs/future_real_collectors.md`), nodos ESP32, Thread/OpenThread, MQTT,
Prometheus, Grafana y ThingsBoard, dentro de la arquitectura general de
observabilidad de la tesis.
