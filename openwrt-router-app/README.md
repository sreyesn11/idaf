# OpenWrt Router Diagnostic App

Mini aplicación web local para administrar, consultar y diagnosticar un
router OpenWrt mediante conexión SSH. Es el primer módulo (nombre interno
`openwrt-router-app`) de una arquitectura de observabilidad y diagnóstico
automático para redes IoT desarrollada como parte de una tesis de maestría.
En esta primera fase el alcance está limitado exclusivamente al router
OpenWrt: no se implementan todavía ESP32, Thread/OpenThread, MQTT,
Prometheus, Grafana ni ThingsBoard, aunque la arquitectura queda preparada
para integrarlos en fases posteriores.

## 1. Descripción

La aplicación permite configurar una conexión SSH a un router OpenWrt,
probar la conectividad, ejecutar comandos de diagnóstico predefinidos
(nunca comandos libres), capturar y estructurar la salida, mostrarla en una
interfaz Streamlit, y guardar tanto un historial en SQLite como evidencias
en archivos JSON.

## 2. Requisitos

- Python 3.11 o superior.
- Acceso SSH a un router OpenWrt (o a un entorno de laboratorio que lo simule).

## 3. Instalación

Clona o copia esta carpeta (`openwrt-router-app/`) y sitúate dentro de ella.

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
menú lateral: Inicio, Conexión, Comandos, Historial y Acerca de.

## 7. Estructura

```text
openwrt-router-app/
├── app.py                      # Página de Inicio (Streamlit)
├── pages/
│   ├── 1_Conexion.py           # Configuración y prueba de conexión SSH
│   ├── 2_Comandos.py           # Selección/ejecución de comandos y resultado
│   ├── 3_Historial.py          # Historial de ejecuciones
│   └── 4_Acerca_de.py
├── core/
│   ├── ssh_client.py           # Conexión y ejecución SSH (Paramiko)
│   ├── command_service.py      # Carga y valida config/commands.yaml
│   ├── execution_service.py    # Orquesta SSH -> parser -> BD -> evidencia
│   ├── logging_config.py       # Logging rotativo a logs/app.log
│   ├── exceptions.py           # Jerarquía de excepciones propias
│   └── constants.py
├── models/                     # Modelos Pydantic (connection, command, execution)
├── parsers/                    # Un parser por formato de salida
├── repositories/               # Persistencia en SQLite (SQLAlchemy)
├── config/
│   ├── commands.yaml           # Lista blanca de comandos permitidos
│   └── settings.yaml           # Política de host key SSH
├── evidence/                   # Evidencias JSON: evidence/YYYY/MM/DD/<execution_id>.json
├── logs/                       # logs/app.log (rotativo)
├── tests/                      # Pruebas unitarias (pytest, sin SSH real)
├── requirements.txt
└── pyproject.toml
```

## 8. Configuración

### 8.1 Comandos permitidos (`config/commands.yaml`)

Cada comando declara `id`, `name`, `description`, `command`, `parser`
(`json`, `text`, `lines`, `uptime`, `free` o `df`), `category`, `timeout` y
`enabled`. Solo se cargan y muestran los comandos con `enabled: true`. No
existe ningún campo de comando libre en la interfaz.

### 8.2 Política de clave de host SSH (`config/settings.yaml`)

```yaml
ssh:
  host_key_policy: auto   # auto | reject
```

`auto` acepta automáticamente claves de host desconocidas (`AutoAddPolicy`)
y solo debe usarse en un laboratorio controlado. `reject` rechaza cualquier
clave de host no registrada previamente.

## 9. Uso

1. En **Conexión**, ingresa host, puerto, usuario, contraseña y timeout, y
   presiona "Probar conexión". La contraseña solo vive en memoria durante
   la sesión de Streamlit.
2. En **Comandos**, filtra por categoría, selecciona un comando de la lista
   blanca y presiona "Ejecutar". El resultado (estado, código de salida,
   duración, stdout, stderr, datos estructurados) se muestra debajo, junto
   con un botón para descargar la evidencia JSON.
3. En **Historial**, filtra por estado/categoría o busca por comando, abre
   el detalle de cualquier ejecución, descarga su evidencia, elimina
   registros individuales o limpia todo el historial (con confirmación).

## 10. Seguridad

- Solo se permiten comandos predefinidos en `config/commands.yaml`; no hay
  entrada de comandos libres ni concatenación de comandos con datos del
  usuario, y no se usa `shell=True`.
- La aplicación no modifica la configuración del router ni ejecuta comandos
  destructivos.
- La contraseña SSH nunca se guarda en SQLite, JSON, YAML, logs ni ningún
  otro almacenamiento persistente; solo permanece en `st.session_state`
  durante la sesión activa de Streamlit.
- Los logs (`logs/app.log`) registran host, usuario, id de comando,
  duración y estado, pero nunca contraseñas ni credenciales.
- Los errores se traducen siempre a un mensaje amigable; nunca se muestra
  un stack trace completo al usuario final.

## 11. Pruebas

```bash
pytest -v
```

Las pruebas cubren carga y validación de `commands.yaml`, cada parser,
los modelos Pydantic y el flujo de `ExecutionService` (éxito, error de
conexión, código de salida distinto de cero, fallo de parsing y escritura
de evidencia). Ninguna prueba abre una conexión SSH real: `SSHClient` se
sustituye por un doble de prueba.

## 12. Limitaciones

- Primera fase limitada al router OpenWrt: no incluye ESP32, Thread/
  OpenThread, MQTT, Prometheus, Grafana ni ThingsBoard.
- No todos los comandos de `commands.yaml` están garantizados en todas las
  versiones/variantes de OpenWrt (por ejemplo, `iwinfo` o `ubus` pueden no
  estar disponibles según la imagen instalada); en ese caso la ejecución
  queda registrada como `FAILED` con el código de salida correspondiente.
- Los parsers de `uptime`, `free` y `df` son de mejor esfuerzo (BusyBox
  varía su formato de salida); si no logran interpretar la salida, el
  resultado se marca `COMPLETED_WITH_WARNINGS` conservando el stdout crudo.

## 13. Próximos pasos

Integración, en fases posteriores, con nodos ESP32, Thread/OpenThread,
MQTT, Prometheus, Grafana y ThingsBoard, dentro de la arquitectura general
de observabilidad de la tesis.
