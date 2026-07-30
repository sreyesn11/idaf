# Cómo conectar un colector real (trabajo futuro)

Este documento describe qué falta para reemplazar `SimulatedDiscoveryCollector` por un colector real — **no implementado en v0.3.0-dev**, deliberadamente (spec sección 2: sin VPN, sin acceso confirmado al Linksys, sin confirmar herramientas disponibles en el firmware).

## 1. El contrato que cualquier colector real debe cumplir

Todo lo que hay debajo de `discovery_service.py` (normalización, correlación, persistencia, evidencia, UI) ya está terminado y probado. Un colector real solo necesita implementar `discovery/collectors/base.py`:

```python
class DiscoveryCollector(Protocol):
    collector_type: CollectorType
    def collect(self) -> list[RawDiscoveryObservation]: ...
```

y producir `RawDiscoveryObservation` con el mismo `raw_payload` que ya consume `discovery/normalization/normalizer.py` (ver `docs/simulated_discovery.md` sección 3 para las claves soportadas: `hostname`, `mac`, `ipv4`, `ipv6`, `agent_id`, `serial`, `thread_ext_address`, `rloc16`, `device_type_hint`, `manufacturer_hint`, `parent_hostname`, `mdns_name`).

Ningún cambio es necesario en `normalization/`, `correlation/`, `services/`, `repositories/`, ni en la página de Streamlit — todos ya son agnósticos a la fuente de los datos.

## 2. Fuentes reales candidatas (por tipo de observación)

| `ObservationType` | Fuente real candidata en OpenWrt/Linksys | Riesgo/bloqueo actual |
|---|---|---|
| `IPV4_NEIGHBOR` | `ip neigh` / tabla ARP del router | Requiere SSH al Linksys — no confirmado |
| `IPV6_NEIGHBOR` | `ip -6 neigh` | Igual que arriba |
| `DHCP_LEASE` | `/tmp/dhcp.leases` (dnsmasq) en OpenWrt | Requiere confirmar que el Linksys corre OpenWrt y dnsmasq |
| `WIFI_CLIENT` | `ubus call hostapd.* get_clients` o `iwinfo assoclist` | Requiere confirmar `ubus`/`iwinfo` disponibles |
| `MDNS_SERVICE` | `avahi-browse`/`umdns` | Requiere confirmar que el paquete está instalado |
| `GATEWAY_REPORT` | Reporte propio de un router/gateway administrado vía SSH (ya tenemos `SSHClient`/`ExecutionService`) | El más viable primero — reutiliza infraestructura SSH ya probada del resto de la app |
| `THREAD_NODE_REPORT` | Border router Thread/OpenThread (`ot-ctl` u OTBR REST API) | Fuera de alcance hasta que exista hardware Thread confirmado en el laboratorio |

## 3. Plan de implementación sugerido (en orden)

1. **`GATEWAY_REPORT` real primero**: es el único tipo que puede construirse reutilizando `core/ssh_client.py` + `core/command_service.py` + `config/commands.yaml` (agregar comandos de solo lectura como `cat /tmp/dhcp.leases`, `ubus call network.wireless status`, etc. a la lista blanca existente — nunca comandos libres, mismo principio de seguridad que el resto de la app).
2. Envolver la salida parseada de esos comandos en `RawDiscoveryObservation` dentro de una clase `SSHDiscoveryCollector` que implemente el mismo `Protocol`.
3. Confirmar en el Linksys real qué herramientas existen (`ubus`, `iwinfo`, `dnsmasq`, `avahi`/`umdns`) antes de intentar `WIFI_CLIENT`/`MDNS_SERVICE` reales — no asumir.
4. Dejar `THREAD_NODE_REPORT` real para cuando haya un border router Thread confirmado; el tipo de observación y sus identificadores (`THREAD_EXT_ADDRESS`, `RLOC16`) ya están validados end-to-end contra el fixture simulado, así que integrar un colector real no debería requerir cambios de modelo.

## 4. Qué NO cambiar al integrar un colector real

- No saltarse la normalización ni la resolución de identidad "porque ya sabemos que es un dato real" — son las que previenen que una IP reciclada fusione dos dispositivos distintos.
- No escribir contraseñas ni tokens en `raw_payload` — la evidencia JSON se guarda en disco tal cual.
- No convertir automáticamente un dispositivo detectado en `MANAGED`: la aprobación sigue siendo manual (spec sección 4.2), incluso con datos reales.
- No asumir que el Linksys usa OpenWrt — verificar primero (spec sección 2, última viñeta antes de la lista de "no").
