# Descubrimiento simulado

## 1. Por qué todo es simulado en esta versión

Al momento de construir IDAF v0.3.0-dev no existe (spec sección 2):

- VPN hacia el laboratorio.
- Acceso remoto autorizado al Linksys.
- Acceso SSH al Linksys.
- Confirmación del firmware exacto del Linksys, ni de que tenga `ubus`, `iw`, `iwinfo`, `dnsmasq`, `avahi`/`umdns` u otras herramientas concretas de descubrimiento.

Por lo tanto, esta versión **no** se conecta a ningún dispositivo real, no escanea la red, y no depende de SSH para arrancar ni para pasar sus pruebas. Todo el pipeline (colección → normalización → correlación → persistencia → inventario → topología) se valida contra un fixture JSON local y corre completo sin ninguna conexión de red.

## 2. `SimulatedDiscoveryCollector`

`discovery/collectors/simulated.py` implementa el `Protocol DiscoveryCollector` (`discovery/collectors/base.py`) leyendo un archivo JSON y produciendo la misma forma (`RawDiscoveryObservation`) que cualquier colector futuro debería producir. Ningún otro módulo del pipeline sabe que el colector es simulado — `discovery_service.py` recibe cualquier objeto que cumpla el protocolo.

```python
from discovery.collectors.simulated import SimulatedDiscoveryCollector, list_available_fixtures

fixtures = list_available_fixtures()  # escanea discovery/collectors/fixtures/*.json
collector = SimulatedDiscoveryCollector(fixtures[0])
observations = collector.collect()  # list[RawDiscoveryObservation]
```

## 3. Formato de fixture

```json
{
  "collector_id": "collector-lab-network",
  "collector_type": "SIMULATED_ROUTER",
  "observed_at": "2026-07-29T18:00:00-05:00",
  "observations": [
    {
      "observation_type": "DHCP_LEASE",
      "source": "router-dhcp",
      "observed_at": "2026-07-29T18:00:01-05:00",
      "payload": {
        "hostname": "esp32-c6-01",
        "mac": "AA:BB:CC:DD:EE:FF",
        "ipv4": "192.168.1.50",
        "ipv6": ["fd00:1daf::50"],
        "agent_id": "...",
        "serial": "...",
        "thread_ext_address": "0011223344556677",
        "rloc16": "0x1001",
        "device_type_hint": "ESP32_C6",
        "manufacturer_hint": "Espressif",
        "parent_hostname": "gw1",
        "mdns_name": "esp32-c6-01.local"
      }
    }
  ]
}
```

Todos los campos de `payload` son opcionales; `discovery/normalization/normalizer.py` extrae los que estén presentes y registra en `normalization_errors` los que fallen validación, sin descartar el resto de la observación. `parent_hostname` es lo que permite a `discovery_service.py` crear los `TopologyLink` padre→hijo (gateway → nodo) una vez que ambos extremos existen como dispositivos.

`observed_at` a nivel de observación es opcional — si falta, se usa el `observed_at` general del fixture.

## 4. `discovery/collectors/fixtures/lab_network.json`

Fixture principal (20 observaciones), representa la red de laboratorio descrita en la spec sección 8.2:

| Dispositivo(s) | Qué demuestra |
|---|---|
| `idaf-server`, `openwrt-one`, `beagleplay-lab`, `rpi-lab`, `gw1`–`gw4` | Inventario base — cada uno con hostname, MAC e IPv4 propios |
| `esp32-c6-01/02/03` (vía `THREAD_NODE_REPORT`) | Identificador `THREAD_EXT_ADDRESS`/`RLOC16`; enlaces `THREAD` hacia su gateway padre |
| `monitor-luz` | Enlace `WIFI` hacia su gateway padre (`gw2`) |
| `iphone-visita` | Dispositivo transitorio (`PHONE`), pensado para ignorarse manualmente en la UI |
| `sensor-dup` | Un mismo MAC observado 3 veces por 3 tipos de observación distintos (`DHCP_LEASE`, `IPV6_NEIGHBOR`, `MDNS_SERVICE`) — deben colapsar en **un** dispositivo, no tres |
| `roamer` | Dos observaciones con la misma MAC pero distinta IPv4 (cambio de IP) — la dirección anterior debe marcarse `is_current=False`, no desaparecer |
| `multi-v6` | Una observación con 3 direcciones IPv6 simultáneas (dos globales/ULA + una link-local) — todas deben quedar `is_current=True` a la vez |
| `ghost-node` | Dispositivo "normal" pensado para ejercitar `InventoryService.mark_stale()` en pruebas/demo (no se auto-marca stale por fecha del fixture; se fuerza con un `older_than` corto) |

## 5. Ejecutar un descubrimiento simulado

**Desde la UI**: página **Descubrimiento** → pestaña "Ejecutar descubrimiento" → elegir el fixture → botón "Ejecutar descubrimiento simulado". Muestra el resumen, el detalle por observación, y permite descargar la evidencia JSON.

**Desde código**:

```python
from discovery.services.discovery_service import DiscoveryService
from discovery.collectors.simulated import SimulatedDiscoveryCollector
# ... construir DiscoveryService con sus 6 repositorios (ver discovery_architecture.md) ...

collector = SimulatedDiscoveryCollector(fixture_path)
evidence = service.run(collector, fixture_name=fixture_path.name)
print(evidence.devices_created, evidence.devices_updated)
```

Correr el mismo fixture dos veces es idempotente: la segunda corrida no crea dispositivos nuevos, solo actualiza `last_seen_at`/identificadores de los ya existentes (`tests/test_discovery_onboarding.py::test_run_is_idempotent_on_second_pass`).

## 6. Agregar un fixture propio

Cualquier archivo `*.json` con el formato de la sección 3, colocado en `discovery/collectors/fixtures/`, aparece automáticamente en el selector de la UI (`list_available_fixtures()` solo escanea el directorio). Útil para representar variantes del laboratorio sin tocar código.
