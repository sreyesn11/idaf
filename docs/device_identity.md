# Modelo de identidad de dispositivos

Cómo el módulo de descubrimiento decide si una observación pertenece a un dispositivo ya conocido, a uno nuevo, o si es ambigua. Implementado en `discovery/correlation/identity_resolver.py`.

## 1. Por qué la IP nunca es la identidad primaria

Una IP puede cambiar (DHCP) y un mismo equipo puede tener varias simultáneamente (varias direcciones IPv6). Usarla como clave primaria fusionaría dispositivos distintos que comparten un momento de red, o separaría el mismo dispositivo en dos cuando cambia de IP. Por eso `IdentifierType.IPV4`/`IPV6` existen — se guardan y se usan como evidencia — pero **nunca alcanzan por sí solas el umbral de fusión automática** (`test_same_ip_alone_is_possible_duplicate_not_auto_matched` en `tests/test_discovery_correlation.py` es la prueba que lo garantiza).

## 2. Orden de prioridad de identificadores (spec sección 4.3)

1. ID interno de IDAF (`InventoryDeviceRecord.id`, implícito — es la clave primaria).
2. `agent_id`
3. Número de serie
4. Thread Extended Address
5. MAC de interfaz
6. Hostname estable
7. Nombre mDNS
8. Combinación de identificadores secundarios (hostname + fabricante)
9. IP — evidencia temporal, nunca identidad primaria

## 3. Tabla de confianza

`IDENTIFIER_CONFIDENCE` en `identity_resolver.py` es la única fuente de verdad de la fórmula — para ajustar la sensibilidad de la correlación, se edita ese diccionario, no la lógica de resolución:

| Identificador | Confianza base | Banda |
|---|---|---|
| `AGENT_ID` | 0.95 | Fuerte |
| `SERIAL` | 0.95 | Fuerte |
| `THREAD_EXT_ADDRESS` | 0.93 | Fuerte |
| `MAC` | 0.90 | Fuerte |
| `MDNS_NAME` | 0.75 | Media |
| `HOSTNAME` + fabricante coincide | 0.75 | Media |
| `RLOC16` | 0.55 | Débil-media |
| `HOSTNAME` solo | 0.50 | Débil |
| `IPV4` / `IPV6` | 0.50 | Débil |

### Bandas de decisión

| Confianza | Resultado (`CorrelationStatus`) |
|---|---|
| ≥ 0.90 | `MATCHED_DEVICE` (coincidencia fuerte) |
| 0.70 – 0.89 | `MATCHED_DEVICE` (coincidencia probable) |
| 0.40 – 0.69 | `POSSIBLE_DUPLICATE` — no se fusiona solo, queda como dispositivo pendiente separado y aparece en la pestaña "Conflictos y duplicados" para revisión manual |
| < 0.40 con al menos un identificador | `NEW_DEVICE` |
| Sin identificadores extraíbles | `INSUFFICIENT_EVIDENCE` |

`MATCHED_DEVICE` reutiliza un umbral único (`MATCH_THRESHOLD = 0.70`) para las bandas "fuerte" y "probable" de la spec: ambas resuelven en una actualización del dispositivo existente, la diferencia entre 0.90 y 0.70 es solo qué tan alto queda registrado el campo `confidence` de la observación — no cambia el resultado binario de la acción tomada.

## 4. Conflicto de identidad

`IDENTITY_CONFLICT` ocurre cuando **dos identificadores fuertes de la misma observación** (por ejemplo, la MAC y el `agent_id`) apuntan a **dos dispositivos ya existentes distintos**. Esto es deliberadamente distinto de "dos observaciones separadas que resultan compartir un identificador débil" — ese segundo caso es responsabilidad de `DuplicateDetector` (que corre sobre todo el inventario, no por observación) y termina en la pestaña "Conflictos y duplicados" como un par de posibles duplicados, no como un `IDENTITY_CONFLICT`.

Ver `tests/test_discovery_correlation.py::test_mac_conflict_between_two_devices_is_identity_conflict`.

## 5. Casos de correlación cubiertos (spec sección 8.3 / 19.2)

| Caso | Dónde se prueba |
|---|---|
| Coincidencia por MAC | `test_matches_by_same_mac` |
| Coincidencia por `agent_id` | `test_matches_by_same_agent_id` |
| Coincidencia por Thread Extended Address | `test_matches_by_same_thread_ext_address` |
| Coincidencia débil por IP (nunca fusiona sola) | `test_same_ip_alone_is_possible_duplicate_not_auto_matched` |
| Hostname compartido sin otra evidencia | `test_shared_hostname_alone_is_weak_evidence` |
| Conflicto de identificadores fuertes | `test_mac_conflict_between_two_devices_is_identity_conflict` |
| Dispositivo nuevo | `test_new_device_when_nothing_matches` |
| Dispositivo manual detectado después por descubrimiento | `test_manual_device_matched_by_later_observation` |
| Evidencia insuficiente | `test_insufficient_evidence_when_no_identifiers` |
| Varias direcciones IPv6 del mismo equipo (no se colapsan) | `tests/test_discovery_persistence.py::test_multiple_ipv6_addresses_stay_current_simultaneously` |
| IP que cambia manteniendo la misma MAC | `tests/test_discovery_persistence.py::test_ipv4_address_upsert_marks_previous_as_not_current` y el escenario `roamer` en `discovery/collectors/fixtures/lab_network.json` |
| Duplicado observado por IPv4 + IPv6 + mDNS en una sola corrida | Escenario `sensor-dup` en el fixture — las tres observaciones comparten MAC y colapsan en un solo dispositivo |

## 6. Cómo ajustar el modelo

- **Cambiar sensibilidad**: editar `IDENTIFIER_CONFIDENCE` o los tres umbrales (`STRONG_MATCH_THRESHOLD`, `MATCH_THRESHOLD`, `POSSIBLE_DUPLICATE_THRESHOLD`) en `identity_resolver.py`.
- **Agregar un identificador nuevo**: extender `IdentifierType` (`discovery/enums.py`), agregar su normalizador en `discovery/normalization/validators.py`, extraerlo en `normalize_observation()`, y darle una confianza base en `IDENTIFIER_CONFIDENCE`.
- **Cambiar qué cuenta como "fuerte"**: editar `_STRONG_IDENTIFIER_TYPES` en `identity_resolver.py` (usado para detectar `IDENTITY_CONFLICT`).
