# Arquitectura del módulo de descubrimiento (IDAF v0.3.0-dev)

Este documento describe el módulo `discovery/` de `openwrt-router-app/`: descubrimiento automático (simulado) e inventario de dispositivos. Complementa `CLAUDE.md`/`README.md`; no reemplaza la documentación general del proyecto.

## 1. Objetivo

Responder: *¿qué dispositivos existen en la red del laboratorio, cómo se relacionan entre sí (gateway → nodo), y cuáles ya fueron revisados y aprobados por un humano?* — sin ejecutar ningún escaneo, conexión SSH, o acceso de red real (ver `docs/simulated_discovery.md` para el porqué).

## 2. Flujo de datos

```text
Colector (RawDiscoveryObservation)
        ↓
Normalización (NormalizedObservation: identificadores/direcciones canónicos)
        ↓
Resolución de identidad (IdentityResolution: NEW_DEVICE | MATCHED_DEVICE |
                          POSSIBLE_DUPLICATE | IDENTITY_CONFLICT |
                          INSUFFICIENT_EVIDENCE)
        ↓
Persistencia (InventoryDevice, DeviceIdentifier, DeviceAddress,
              DeviceInterface, DiscoveryObservation, TopologyLink)
        ↓
Aprobación / edición / fusión / ignorar (OnboardingService)
        ↓
Inventario + Topología (InventoryService, topology.builder)
```

Cada flecha es un límite de módulo real, no solo una nota de diseño: `discovery/services/discovery_service.py` es el único punto que conoce las cinco etapas en orden; todo lo demás solo conoce su propia entrada/salida. Esto es intencional (spec sección 4.1): ninguna página de Streamlit ni ningún servicio mezcla adquisición, normalización, correlación y persistencia en un solo bloque.

## 3. Paquete `discovery/`

```text
discovery/
├── enums.py                     # DeviceDiscoveryStatus, DeviceManagementStatus, DeviceType,
│                                 # IdentifierType, ObservationType, CorrelationStatus,
│                                 # CollectorType, LinkType, AddressFamily, AddressScope
├── models.py                    # Modelos Pydantic en memoria (no persistidos): RawDiscoveryObservation,
│                                 # NormalizedObservation, IdentityResolution, DiscoveryRunEvidence, MergePreview
├── collectors/
│   ├── base.py                  # Protocol DiscoveryCollector — la única interfaz que el resto del
│   │                             # pipeline conoce; no importa nada de SSH/OpenWrt/Linksys.
│   ├── simulated.py             # SimulatedDiscoveryCollector: lee un fixture JSON y produce
│   │                             # RawDiscoveryObservation — mismo contrato que un colector real futuro.
│   └── fixtures/
│       └── lab_network.json     # Ver docs/simulated_discovery.md
├── normalization/
│   ├── validators.py            # Funciones puras: normalize_mac, normalize_ipv4, normalize_ipv6,
│   │                             # normalize_hostname, normalize_mdns_name, normalize_thread_ext_address,
│   │                             # normalize_timestamp — cada una levanta ValueError, nunca falla en silencio.
│   └── normalizer.py            # normalize_observation(): orquesta los validadores sobre un
│                                 # RawDiscoveryObservation, acumulando errores en vez de abortar.
├── correlation/
│   ├── identity_resolver.py     # DeviceIdentityResolver — ver docs/device_identity.md
│   ├── duplicate_detector.py    # DuplicateDetector: escanea todo el inventario en busca de pares
│   │                             # de dispositivos que comparten un identificador (para la pestaña
│   │                             # "Conflictos y duplicados", no se ejecuta por observación).
│   └── merge_planner.py         # MergePlanner: fusión transaccional (ver sección 6).
├── services/
│   ├── discovery_service.py     # Orquesta colector → normalizador → resolver → repositorios → evidencia.
│   ├── onboarding_service.py    # approve / edit_and_approve / ignore / restore / merge.
│   └── inventory_service.py     # Lecturas agregadas para la UI + mark_stale().
└── repositories/
    ├── inventory_device_repository.py  # tabla `inventory_devices`
    ├── identifier_repository.py        # tabla `device_identifiers`
    ├── address_repository.py           # tabla `device_addresses`
    ├── interface_repository.py         # tabla `device_interfaces`
    ├── observation_repository.py       # tabla `discovery_observations`
    └── topology_link_repository.py     # tabla `topology_links`
```

## 4. Por qué `inventory_devices` es una tabla separada de `devices`

`repositories/device_repository.py` (`devices`) ya existía: es el registro estricto de *gateways administrables por SSH* que usan Conexión/Comandos/Diagnóstico, y nunca tuvo columna de contraseña. `inventory_devices` es un concepto más amplio — cualquier cosa detectada en la red (sensores, nodos ESP32, teléfonos transitorios, el propio servidor IDAF) — la mayoría de los cuales **nunca** tendrán una conexión SSH administrada.

`InventoryDeviceRecord.gateway_id` es un FK opcional hacia `devices.id`: el puente entre ambos mundos es *"este dispositivo de inventario, cuando está aprobado, además resulta ser un gateway SSH administrado"* — no una fusión de las dos tablas. Ningún dato de `devices` se modificó; ver `CLAUDE.md` sección "Commands are data, not code" — esta separación sigue el mismo principio de capas del resto del proyecto.

## 5. Estados y transiciones

`DeviceDiscoveryStatus`: `DISCOVERED → PENDING_APPROVAL → APPROVED`, con salidas laterales a `IGNORED` (y de vuelta a `PENDING_APPROVAL`/`APPROVED` vía `restore()`), `STALE` (por inactividad, ver `InventoryService.mark_stale()`), y `REMOVED` (solo como resultado de una fusión — nunca se borra una fila físicamente, spec sección 11).

Ningún colector ni normalizador puede escribir `APPROVED` directamente: esa transición vive únicamente en `OnboardingService.approve()`/`edit_and_approve()`. El registro manual (`pages/7_Descubrimiento.py`, pestaña "Registro manual") es la única otra vía directa a `APPROVED`, porque un dispositivo tecleado a mano por el operador ya está, por definición, revisado.

## 6. Fusión transaccional

`MergePlanner.merge()` abre una sola sesión SQLAlchemy, reasigna `device_id`/`resolved_device_id`/`source_device_id`/`target_device_id` en las seis tablas dependientes con `UPDATE ... WHERE`, marca el origen como `REMOVED` (nunca lo borra) y hace `commit()` una sola vez al final. Cualquier excepción antes de ese `commit()` dispara `session.rollback()` — nada queda parcialmente movido. Ver `tests/test_discovery_persistence.py::TestMergeTransaction::test_merge_rolls_back_on_failure` para la prueba que fuerza un fallo a mitad de camino y verifica que el origen queda intacto.

## 7. Evidencia y trazabilidad

Cada corrida de `DiscoveryService.run()` escribe un JSON en `evidence/discovery/YYYY/MM/DD/<execution_id>.json` con la forma de `DiscoveryRunEvidence` (spec sección 17) — nunca contiene contraseñas. Cada observación individual, además, queda persistida en `discovery_observations` con su payload crudo y normalizado, su `correlation_status` y el `resolved_device_id` (si lo hubo), satisfaciendo el requisito de trazabilidad completa de la spec (sección 4.4): origen, colector, fecha, datos normalizados, datos crudos, confianza, dispositivo observado y resultado de correlación.

## 8. Integración con topología

`topology/builder.py::build_inventory_topology()` construye un grafo a partir de `InventoryDeviceRecord` + `TopologyLinkRecord`, reutilizando el mismo `TopologyGraph`/`TopologyNode`/`TopologyLink` (Pydantic, en memoria) que ya usaba el diagrama PC↔router — no se creó un segundo modelo de grafo. El estado de cada nodo es una traducción aproximada de `discovery_status` a `DiagnosticState` (solo para reutilizar la paleta de colores existente; nunca es un diagnóstico real). Un enlace en el grafo siempre viene de una fila `TopologyLinkRecord` ya persistida — nunca de una coincidencia de IP entre dos observaciones (spec sección 15, última viñeta).

El diagrama animado de dos nodos (`render_topology()`) no se tocó. La vista de inventario usa un render nuevo, `render_inventory_tree()`, en forma de árbol indentado con `st.markdown` — ver la nota de diseño en el propio docstring de esa función sobre por qué no se extendió el HTML/CSS del diagrama original a N nodos.

## 9. Qué NO hace esta versión

- No ejecuta descubrimiento contra hardware real (ver `docs/simulated_discovery.md`).
- No calcula un "health score" del inventario ni usa machine learning para la resolución de identidad — es una tabla de confianza documentada y editable (`docs/device_identity.md`).
- No implementa Thread/OpenThread, MQTT, Prometheus, Grafana ni ThingsBoard — el tipo de observación `THREAD_NODE_REPORT` existe únicamente para validar que el modelo de datos ya los puede representar (ver `docs/future_real_collectors.md`).
