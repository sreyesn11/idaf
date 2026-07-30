# Changelog

Formato libre, en español, orientado a la tesis IDAF. No se sigue
estrictamente Keep a Changelog/SemVer todavía porque el proyecto está en
fase de desarrollo académico continuo, pero cada entrada indica qué
versión introdujo qué.

## v0.3.0-dev — Descubrimiento e inventario de dispositivos (simulado)

Módulo nuevo `discovery/`: descubrimiento automático (simulado) e
inventario de dispositivos, sin tocar ninguna funcionalidad existente.

### Agregado

- Paquete `discovery/` completo: enums de dominio, modelos Pydantic en
  memoria, colector simulado + interfaz `DiscoveryCollector`,
  normalización (MAC/IPv4/IPv6/hostname/mDNS/Thread Extended
  Address/timestamps), resolución de identidad con tabla de confianza
  documentada, detector de duplicados, planificador de fusión
  transaccional, y tres servicios (`DiscoveryService`,
  `OnboardingService`, `InventoryService`).
- Seis tablas nuevas en SQLite (creadas automáticamente, sin tocar el
  esquema existente): `inventory_devices`, `device_identifiers`,
  `device_addresses`, `device_interfaces`, `discovery_observations`,
  `topology_links`.
- Página Streamlit **Descubrimiento** (`pages/7_Descubrimiento.py`): 7
  pestañas — Resumen, Ejecutar descubrimiento, Pendientes, Inventario,
  Ignorados, Conflictos y duplicados, Registro manual.
- Fixture simulado `discovery/collectors/fixtures/lab_network.json` (20
  observaciones) cubriendo todos los casos de correlación de la spec:
  coincidencia por MAC/agent_id/Thread Extended Address, IP sola nunca
  fusiona, hostname compartido débil, duplicado observado por
  IPv4+IPv6+mDNS, IP que cambia manteniendo la MAC, múltiples IPv6
  simultáneas, y relaciones padre-hijo (gateway → nodo) para topología.
- `topology/builder.py::build_inventory_topology()` +
  `topology/renderer.py::render_inventory_tree()`: vista de árbol del
  inventario en la página **Topología**, independiente del diagrama
  animado PC↔router existente (que no se modificó).
- Evidencia JSON por corrida de descubrimiento en
  `evidence/discovery/YYYY/MM/DD/<execution_id>.json`.
- 61 pruebas nuevas (normalización, correlación, persistencia —incluyendo
  reversión de fusión ante fallo—, flujo de onboarding, topología),
  ninguna abre conexión de red real.
- Documentación nueva: `docs/discovery_architecture.md`,
  `docs/device_identity.md`, `docs/simulated_discovery.md`,
  `docs/future_real_collectors.md`.

### Corregido (efecto colateral necesario, no una funcionalidad nueva)

- `repositories/database.py`: se agregó el helper `naive()` — SQLite
  descarta la zona horaria de las columnas `datetime` al guardarlas, así
  que comparar un valor recién creado (con tz) contra uno leído de la base
  (sin tz) lanzaba `TypeError`. Este bug ya existía latente en el patrón
  compartido de repositorios pero nunca se había disparado porque ningún
  repositorio anterior comparaba timestamps con `>`/`<`; los nuevos
  repositorios de `discovery/` sí lo hacen (`touch_last_seen`,
  `mark_stale`, los `upsert` de identificadores/direcciones/enlaces), así
  que se corrigió en el helper compartido en vez de solo en el código
  nuevo.

### Sin cambios (verificado)

- Las 107 pruebas existentes del proyecto siguen pasando sin
  modificación.
- `devices` (registro de gateways SSH), `executions`, `diagnostics`,
  `events` — ninguna tabla ni repositorio existente se modificó. El
  puente entre el inventario nuevo y el registro SSH existente es
  `InventoryDeviceRecord.gateway_id` (FK opcional hacia `devices.id`), no
  una fusión de esquemas.
- Ningún flujo de SSH/diagnóstico/comandos cambió de comportamiento.

## v0.2.0 — Primer diagnóstico general del router OpenWrt

Diagnóstico consolidado "Router General Health", historial de
diagnósticos, eventos de cambio de estado, topología mínima PC↔router.

## v0.1.0 — MVP

Conexión SSH, registro de gateways, ejecución de comandos desde lista
blanca, historial de ejecuciones, evidencia JSON.
