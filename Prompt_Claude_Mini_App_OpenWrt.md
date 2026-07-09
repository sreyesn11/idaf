# Prompt para Claude: Mini App de Gestión y Diagnóstico de Router OpenWrt

## Contexto del proyecto

Necesito desarrollar una mini aplicación web local en Python para administrar, consultar y diagnosticar un router OpenWrt mediante conexión SSH.

Esta aplicación formará parte de una tesis de maestría enfocada en una arquitectura de observabilidad y diagnóstico automático para redes IoT. Sin embargo, en esta primera fase el alcance debe estar completamente limitado al router OpenWrt.

No debes implementar todavía comunicación directa con nodos ESP32, Thread/OpenThread, MQTT, Prometheus, Grafana ni ThingsBoard. La aplicación debe quedar preparada arquitectónicamente para integrar esos componentes en fases posteriores, pero el MVP debe trabajar únicamente con el router.

---

# 1. Objetivo principal

Construir una mini aplicación web local que permita:

1. Configurar los datos de conexión SSH del router.
2. Validar la conectividad con el router.
3. Ejecutar comandos seguros y previamente autorizados.
4. Capturar la salida estándar, errores, código de retorno y duración.
5. Mostrar los resultados de manera clara en la interfaz.
6. Convertir, cuando sea posible, las respuestas crudas en datos estructurados.
7. Guardar un historial local de ejecuciones.
8. Generar evidencias en archivos JSON.
9. Mantener una arquitectura modular para agregar nuevas consultas diagnósticas en el futuro.
10. Diferenciar claramente entre:
   - conexión SSH;
   - ejecución del comando;
   - parsing;
   - almacenamiento;
   - presentación del resultado.

---

# 2. Tecnologías obligatorias

Usa las siguientes tecnologías:

- Python 3.11 o superior.
- Streamlit para la interfaz web.
- Paramiko para SSH.
- Pydantic para modelos y validación.
- SQLite para historial.
- SQLAlchemy para acceso a SQLite.
- PyYAML para configuración.
- Python logging para logs.
- pytest para pruebas unitarias.

No uses en esta primera versión:

- React.
- Node.js.
- Django.
- Flask.
- Redis.
- Celery.
- Kafka.
- Docker.
- PostgreSQL.
- Bases de datos externas.
- Servicios en la nube.

---

# 3. Restricciones importantes

La aplicación debe ser local y ejecutarse en el computador del usuario.

No debe modificar la configuración del router.

No debe permitir inicialmente comandos libres.

No debe ejecutar comandos destructivos.

No debe almacenar contraseñas.

No debe registrar contraseñas en logs.

No debe mostrar stack traces completos al usuario final.

No debe asumir que todos los comandos están disponibles en todas las versiones de OpenWrt.

Debe manejar de forma controlada:

- timeout;
- error de autenticación;
- host no alcanzable;
- puerto cerrado;
- comando inexistente;
- salida vacía;
- salida JSON inválida;
- pérdida de conexión;
- error de parsing.

---

# 4. Alcance funcional

## 4.1 Configuración de conexión

La interfaz debe permitir ingresar:

- Dirección IP o hostname.
- Puerto SSH.
- Usuario.
- Contraseña.
- Timeout.

Valores sugeridos:

```text
IP: 192.168.1.1
Puerto: 22
Usuario: root
Timeout: 10
```

La contraseña debe ingresarse en un campo oculto.

La contraseña solo puede mantenerse en memoria durante la sesión de Streamlit.

No debe guardarse en:

- SQLite;
- archivos JSON;
- archivos YAML;
- logs;
- variables persistentes;
- historial.

---

## 4.2 Prueba de conexión

Debe existir un botón:

```text
Probar conexión
```

Al presionarlo, la aplicación debe:

1. Abrir una conexión SSH.
2. Ejecutar:

```bash
echo IDAF_ROUTER_CONNECTION_OK
```

3. Verificar que la salida contiene:

```text
IDAF_ROUTER_CONNECTION_OK
```

4. Mostrar:

- conexión exitosa o fallida;
- host;
- puerto;
- usuario;
- tiempo de conexión;
- mensaje amigable;
- detalle técnico resumido si hubo error.

Debe diferenciar entre:

- fallo de red;
- fallo de autenticación;
- timeout;
- error SSH;
- error desconocido.

---

## 4.3 Comandos predefinidos

No se debe permitir escribir comandos libres.

Los comandos deben definirse en:

```text
config/commands.yaml
```

Usa esta estructura base:

```yaml
commands:
  - id: get_system_board
    name: Información general del router
    description: Obtiene modelo, hostname, kernel y versión de OpenWrt.
    command: ubus call system board
    parser: json
    category: sistema
    timeout: 10
    enabled: true

  - id: get_uptime
    name: Tiempo de actividad
    description: Consulta el tiempo de actividad y carga del router.
    command: uptime
    parser: uptime
    category: sistema
    timeout: 10
    enabled: true

  - id: get_memory
    name: Estado de memoria
    description: Consulta el uso de memoria del sistema.
    command: free
    parser: free
    category: sistema
    timeout: 10
    enabled: true

  - id: get_disk_usage
    name: Uso de almacenamiento
    description: Consulta el uso del almacenamiento.
    command: df -h
    parser: df
    category: sistema
    timeout: 10
    enabled: true

  - id: get_interfaces
    name: Interfaces de red
    description: Consulta interfaces IPv4 e IPv6.
    command: ip addr show
    parser: text
    category: red
    timeout: 10
    enabled: true

  - id: get_ipv6_interfaces
    name: Direcciones IPv6
    description: Consulta las direcciones IPv6 configuradas.
    command: ip -6 addr show
    parser: text
    category: red
    timeout: 10
    enabled: true

  - id: get_ipv6_routes
    name: Rutas IPv6
    description: Consulta la tabla de enrutamiento IPv6.
    command: ip -6 route show
    parser: text
    category: red
    timeout: 10
    enabled: true

  - id: get_network_status
    name: Estado de interfaces OpenWrt
    description: Consulta el estado general de las interfaces administradas por OpenWrt.
    command: ubus call network.interface dump
    parser: json
    category: red
    timeout: 15
    enabled: true

  - id: get_wireless_status
    name: Estado inalámbrico
    description: Consulta radios e interfaces inalámbricas.
    command: ubus call network.wireless status
    parser: json
    category: wifi
    timeout: 15
    enabled: true

  - id: get_wireless_clients
    name: Clientes inalámbricos
    description: Consulta estaciones asociadas a las interfaces WiFi.
    command: iwinfo
    parser: text
    category: wifi
    timeout: 15
    enabled: true

  - id: get_processes
    name: Procesos activos
    description: Consulta procesos activos del router.
    command: ps
    parser: text
    category: sistema
    timeout: 10
    enabled: true

  - id: get_services
    name: Servicios habilitados
    description: Consulta servicios disponibles en init.d.
    command: ls -1 /etc/init.d
    parser: lines
    category: sistema
    timeout: 10
    enabled: true

  - id: get_listening_ports
    name: Puertos en escucha
    description: Consulta puertos TCP y UDP en escucha.
    command: netstat -tuln 2>/dev/null || ss -tuln
    parser: text
    category: red
    timeout: 10
    enabled: true

  - id: get_kernel_log
    name: Últimos eventos del kernel
    description: Consulta las últimas líneas del log del kernel.
    command: dmesg | tail -n 50
    parser: lines
    category: logs
    timeout: 10
    enabled: true

  - id: get_system_log
    name: Últimos eventos del sistema
    description: Consulta las últimas líneas del log del sistema.
    command: logread | tail -n 50
    parser: lines
    category: logs
    timeout: 10
    enabled: true
```

La aplicación debe filtrar únicamente comandos con:

```yaml
enabled: true
```

---

# 5. Interfaz requerida

La aplicación debe tener como mínimo cinco secciones.

## 5.1 Inicio

Debe mostrar:

- título;
- descripción;
- estado de conexión;
- último comando ejecutado;
- total de ejecuciones;
- ejecuciones exitosas;
- ejecuciones fallidas;
- versión del sistema.

## 5.2 Conexión

Debe permitir:

- configurar host;
- configurar puerto;
- configurar usuario;
- configurar timeout;
- ingresar contraseña;
- probar conexión.

## 5.3 Comandos

Debe permitir:

- filtrar por categoría;
- seleccionar comando;
- ver nombre;
- ver descripción;
- ver comando exacto;
- ver timeout;
- ejecutar.

No debe haber campo libre para comandos.

## 5.4 Resultados

Debe mostrar:

- estado;
- código de salida;
- duración;
- fecha y hora;
- stdout;
- stderr;
- datos estructurados;
- mensaje amigable;
- detalle técnico;
- botón para descargar evidencia JSON.

## 5.5 Historial

Debe mostrar una tabla con:

- ID;
- fecha;
- host;
- usuario;
- comando;
- categoría;
- estado;
- código de salida;
- duración.

Debe permitir:

- filtrar por estado;
- filtrar por categoría;
- buscar por comando;
- abrir detalle;
- descargar evidencia;
- eliminar registros individualmente;
- limpiar historial con confirmación.

---

# 6. Estados de ejecución

Usa estos estados:

```text
CREATED
CONNECTING
RUNNING
COMPLETED
COMPLETED_WITH_WARNINGS
FAILED
TIMEOUT
```

Reglas sugeridas:

- `COMPLETED`: exit code 0 y sin stderr relevante.
- `COMPLETED_WITH_WARNINGS`: exit code 0, pero hay advertencias o parsing parcial.
- `FAILED`: exit code diferente de 0 o error de conexión.
- `TIMEOUT`: se superó el tiempo máximo.
- `CONNECTING`: durante apertura SSH.
- `RUNNING`: comando en ejecución.

---

# 7. Resultado estructurado

Cada ejecución debe producir un objeto como:

```json
{
  "execution_id": "exec-20260708-000001",
  "command_id": "get_system_board",
  "command_name": "Información general del router",
  "category": "sistema",
  "host": "192.168.1.1",
  "port": 22,
  "username": "root",
  "command": "ubus call system board",
  "status": "COMPLETED",
  "exit_code": 0,
  "started_at": "2026-07-08T20:15:00-05:00",
  "finished_at": "2026-07-08T20:15:01-05:00",
  "duration_seconds": 0.85,
  "stdout": "{...}",
  "stderr": "",
  "parsed_data": {
    "hostname": "OpenWrt",
    "model": "OpenWrt One"
  },
  "user_message": "Consulta ejecutada correctamente.",
  "technical_message": null
}
```

Nunca incluir:

- contraseña;
- claves privadas;
- tokens;
- credenciales.

---

# 8. Arquitectura del proyecto

Usa esta estructura:

```text
openwrt-router-app/
│
├── app.py
│
├── pages/
│   ├── 1_Conexion.py
│   ├── 2_Comandos.py
│   ├── 3_Historial.py
│   └── 4_Acerca_de.py
│
├── core/
│   ├── ssh_client.py
│   ├── command_service.py
│   ├── execution_service.py
│   ├── exceptions.py
│   └── constants.py
│
├── models/
│   ├── connection.py
│   ├── command.py
│   └── execution.py
│
├── parsers/
│   ├── base.py
│   ├── json_parser.py
│   ├── text_parser.py
│   ├── lines_parser.py
│   ├── uptime_parser.py
│   ├── free_parser.py
│   └── df_parser.py
│
├── repositories/
│   ├── database.py
│   └── execution_repository.py
│
├── config/
│   ├── commands.yaml
│   └── settings.yaml
│
├── evidence/
│
├── logs/
│
├── tests/
│   ├── test_command_loader.py
│   ├── test_parsers.py
│   ├── test_models.py
│   └── test_execution_service.py
│
├── requirements.txt
├── README.md
├── .gitignore
└── pyproject.toml
```

---

# 9. Responsabilidades por componente

## `ssh_client.py`

Debe:

- abrir conexión;
- cerrar conexión;
- ejecutar comando;
- capturar stdout;
- capturar stderr;
- obtener exit code;
- manejar timeout;
- traducir errores técnicos a excepciones propias.

Usa context manager si es posible.

## `command_service.py`

Debe:

- cargar YAML;
- validar comandos;
- filtrar `enabled`;
- buscar por ID;
- devolver categorías;
- impedir comandos no registrados.

## `execution_service.py`

Debe:

- recibir conexión y comando;
- ejecutar SSH;
- llamar parser;
- construir resultado;
- guardar SQLite;
- guardar evidencia JSON;
- devolver objeto final.

## `repositories`

Debe manejar persistencia.

## `parsers`

Cada parser debe implementar una interfaz común.

Ejemplo:

```python
class BaseParser:
    def parse(self, raw_output: str) -> dict:
        raise NotImplementedError
```

---

# 10. Seguridad SSH

Para el MVP se puede permitir `AutoAddPolicy`, pero debes:

1. Encapsularlo.
2. Añadir comentario indicando que solo es para laboratorio.
3. Dejar preparado un modo estricto.
4. Permitir configurar:

```yaml
ssh:
  host_key_policy: auto
```

Valores posibles:

```text
auto
reject
```

No uses comandos concatenados desde entrada del usuario.

No uses `shell=True`.

No construyas comandos con parámetros sin validar.

---

# 11. Base de datos

Usa SQLite.

Tabla sugerida:

```text
executions
```

Campos:

- id;
- execution_id;
- command_id;
- command_name;
- category;
- host;
- port;
- username;
- command;
- status;
- exit_code;
- started_at;
- finished_at;
- duration_seconds;
- stdout;
- stderr;
- parsed_data_json;
- user_message;
- technical_message;
- evidence_path.

No almacenar contraseña.

---

# 12. Evidencias JSON

Guardar cada ejecución en:

```text
evidence/YYYY/MM/DD/
```

Formato del archivo:

```text
<execution_id>.json
```

Ejemplo:

```text
evidence/2026/07/08/exec-20260708-000001.json
```

La escritura debe ser segura y usar UTF-8.

---

# 13. Logs

Usa archivo rotativo.

Archivo:

```text
logs/app.log
```

Registrar:

- inicio;
- fin;
- host;
- usuario;
- comando ID;
- duración;
- estado;
- errores.

No registrar:

- contraseña;
- stdout sensible completo si contiene secretos;
- credenciales;
- claves.

---

# 14. Parsers mínimos

Implementa:

## JSON parser

Para comandos `ubus`.

Debe manejar:

- JSON válido;
- JSON vacío;
- JSON inválido.

## Text parser

Debe devolver:

```json
{
  "raw_text": "..."
}
```

## Lines parser

Debe devolver:

```json
{
  "lines": ["linea 1", "linea 2"]
}
```

## Uptime parser

Debe intentar extraer:

- hora;
- uptime;
- usuarios;
- carga 1m;
- carga 5m;
- carga 15m.

## Free parser

Debe intentar extraer:

- memoria total;
- usada;
- libre;
- compartida;
- buffers/cache;
- disponible.

## DF parser

Debe extraer por filesystem:

- filesystem;
- size;
- used;
- available;
- use_percent;
- mountpoint.

Si un parser falla, no debe perderse la salida cruda.

Debe marcar:

```text
COMPLETED_WITH_WARNINGS
```

---

# 15. Manejo de errores

Crea excepciones propias:

```python
class RouterAppError(Exception):
    pass

class SSHConnectionError(RouterAppError):
    pass

class SSHAuthenticationError(RouterAppError):
    pass

class SSHTimeoutError(RouterAppError):
    pass

class CommandNotAllowedError(RouterAppError):
    pass

class CommandExecutionError(RouterAppError):
    pass

class ParserError(RouterAppError):
    pass
```

La interfaz debe mostrar mensajes amigables.

Ejemplos:

```text
No fue posible contactar el router.
Verifica la IP, el puerto y la conectividad de red.
```

```text
La autenticación SSH fue rechazada.
Verifica el usuario y la contraseña.
```

```text
El comando no está autorizado.
```

---

# 16. Pruebas unitarias

Crea pruebas para:

- carga de YAML;
- validación de comandos;
- filtro `enabled`;
- búsqueda por ID;
- parser JSON;
- parser uptime;
- parser free;
- parser df;
- modelo Pydantic;
- almacenamiento SQLite;
- generación de evidencia;
- manejo de errores.

No realices conexiones SSH reales en las pruebas.

Usa mocks.

---

# 17. README obligatorio

Incluye:

1. Descripción.
2. Requisitos.
3. Instalación.
4. Creación de entorno virtual.
5. Instalación de dependencias.
6. Ejecución.
7. Estructura.
8. Configuración.
9. Uso.
10. Seguridad.
11. Pruebas.
12. Limitaciones.
13. Próximos pasos.

Comandos sugeridos:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux:

```bash
source venv/bin/activate
```

Instalación:

```bash
pip install -r requirements.txt
```

Ejecución:

```bash
streamlit run app.py
```

Pruebas:

```bash
pytest -v
```

---

# 18. Criterios de aceptación

La solución será aceptada si cumple lo siguiente:

1. La app inicia sin errores.
2. La interfaz permite ingresar conexión.
3. La contraseña no se almacena.
4. El botón de prueba valida SSH.
5. Los comandos se cargan desde YAML.
6. No existe campo de comando libre.
7. Se ejecuta `ubus call system board`.
8. Se captura stdout.
9. Se captura stderr.
10. Se captura exit code.
11. Se calcula duración.
12. Se parsea JSON.
13. Se guarda historial.
14. Se genera evidencia JSON.
15. Se muestran errores amigables.
16. Se puede descargar evidencia.
17. Los tests pasan.
18. El README explica todo.
19. La arquitectura es modular.
20. El código está tipado y comentado.
21. No hay credenciales en el repositorio.
22. No se implementa todavía Thread, MQTT, Prometheus ni Grafana.

---

# 19. Entrega esperada

Entrega todos los archivos completos.

No entregues solo fragmentos.

No omitas:

- imports;
- modelos;
- configuración;
- base de datos;
- pruebas;
- requirements;
- README;
- YAML;
- `.gitignore`.

La aplicación debe poder ejecutarse después de:

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

# 20. Forma de trabajo

Desarrolla la solución en este orden:

1. Presenta la arquitectura.
2. Muestra la estructura del proyecto.
3. Explica decisiones.
4. Genera archivos completos.
5. Verifica consistencia.
6. Corrige imports.
7. Asegura que las rutas funcionen.
8. Incluye instrucciones de ejecución.
9. Incluye pruebas.
10. Finaliza con una lista de validación.

No simplifiques el diseño hasta convertirlo en un único archivo.

Debe ser una base modular y mantenible.

---

# 21. Primera prueba obligatoria

El primer caso que debe funcionar es:

```text
Interfaz Streamlit
→ conexión SSH
→ router OpenWrt
→ ejecución de ubus call system board
→ captura de salida
→ parsing JSON
→ visualización
→ almacenamiento
→ evidencia JSON
```

Esta prueba debe ser prioritaria.

---

# 22. Nombre del proyecto

Usa como nombre visible:

```text
OpenWrt Router Diagnostic App
```

Y como nombre interno:

```text
openwrt-router-app
```

No uses todavía el nombre final completo del framework de tesis, porque esta aplicación corresponde únicamente al módulo de manejo del router.
