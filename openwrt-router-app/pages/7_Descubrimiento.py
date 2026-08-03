from __future__ import annotations

from datetime import datetime

import streamlit as st

from core.exceptions import RouterAppError
from core.formatting import format_datetime
from core.icons import ICONS
from discovery.collectors.simulated import SimulatedDiscoveryCollector, list_available_fixtures
from discovery.collectors.windows_commands import get_net_ip_configuration
from discovery.collectors.windows_neighbor import WindowsNeighborCollector
from discovery.config import load_discovery_config
from discovery.correlation.merge_planner import MergePlanner
from discovery.enums import AddressFamily, AddressScope, DeviceDiscoveryStatus, DeviceManagementStatus, DeviceType, IdentifierType
from discovery.normalization.validators import normalize_hostname, normalize_ipv4, normalize_mac, normalize_thread_ext_address
from discovery.repositories.address_repository import DeviceAddressRepository
from discovery.repositories.identifier_repository import DeviceIdentifierRepository
from discovery.repositories.interface_repository import DeviceInterfaceRepository
from discovery.repositories.inventory_device_repository import InventoryDeviceRepository
from discovery.repositories.observation_repository import DiscoveryObservationRepository
from discovery.repositories.topology_link_repository import TopologyLinkRepository
from discovery.services.discovery_service import DiscoveryService
from discovery.services.inventory_service import InventoryService
from discovery.services.onboarding_service import OnboardingService


@st.cache_resource
def get_inventory_device_repository() -> InventoryDeviceRepository:
    return InventoryDeviceRepository()


@st.cache_resource
def get_identifier_repository() -> DeviceIdentifierRepository:
    return DeviceIdentifierRepository()


@st.cache_resource
def get_address_repository() -> DeviceAddressRepository:
    return DeviceAddressRepository()


@st.cache_resource
def get_interface_repository() -> DeviceInterfaceRepository:
    return DeviceInterfaceRepository()


@st.cache_resource
def get_observation_repository() -> DiscoveryObservationRepository:
    return DiscoveryObservationRepository()


@st.cache_resource
def get_topology_link_repository() -> TopologyLinkRepository:
    return TopologyLinkRepository()


@st.cache_resource
def get_discovery_service() -> DiscoveryService:
    return DiscoveryService(
        get_inventory_device_repository(),
        get_identifier_repository(),
        get_address_repository(),
        get_interface_repository(),
        get_observation_repository(),
        get_topology_link_repository(),
    )


@st.cache_resource
def get_inventory_service() -> InventoryService:
    return InventoryService(
        get_inventory_device_repository(),
        get_identifier_repository(),
        get_address_repository(),
        get_interface_repository(),
        get_observation_repository(),
    )


@st.cache_resource
def get_onboarding_service() -> OnboardingService:
    return OnboardingService(get_inventory_device_repository(), MergePlanner())


_STATUS_LABELS = {
    DeviceDiscoveryStatus.PENDING_APPROVAL.value: "Pendiente de aprobación",
    DeviceDiscoveryStatus.APPROVED.value: "Administrado / aprobado",
    DeviceDiscoveryStatus.IGNORED.value: "Ignorado",
    DeviceDiscoveryStatus.STALE.value: "Sin observar (stale)",
    DeviceDiscoveryStatus.DISCOVERED.value: "Descubierto",
    DeviceDiscoveryStatus.REMOVED.value: "Fusionado / eliminado",
}


def _render_run_result(evidence) -> None:
    if evidence.errors:
        st.warning(f"El descubrimiento terminó con {len(evidence.errors)} advertencia(s) de normalización.")
        with st.expander("Ver advertencias"):
            for error in evidence.errors:
                st.caption(f"{ICONS['warning']} {error}")
    else:
        st.success("Descubrimiento completado sin errores de normalización.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Observaciones recibidas", evidence.observations_received)
    col2.metric("Dispositivos creados", evidence.devices_created)
    col3.metric("Dispositivos actualizados", evidence.devices_updated)
    col4.metric("Conflictos de identidad", evidence.identity_conflicts)

    if evidence.interface is not None:
        col1, col2, col3 = st.columns(3)
        col1.metric("Vecinos IPv4 crudos", evidence.raw_ipv4_neighbors)
        col2.metric("Vecinos IPv6 crudos", evidence.raw_ipv6_neighbors)
        col3.metric("Entradas filtradas", evidence.filtered_entries)

    st.markdown(f"**{ICONS['list']} Detalle por observación**")
    st.dataframe(
        [
            {
                "Tipo": r.observation_type,
                "Origen": r.source,
                "Resultado": r.correlation_status,
                "Confianza": round(r.confidence, 2),
                "Dispositivo": r.device_name or "-",
                "Notas": r.notes or "",
            }
            for r in evidence.results
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        f"{ICONS['download']} Descargar evidencia JSON",
        data=evidence.model_dump_json(indent=2),
        file_name=f"{evidence.execution_id}.json",
        mime="application/json",
        key=f"download_evidence_{evidence.execution_id}",
    )
    st.caption(f"ID de ejecución: `{evidence.execution_id}`")


def _device_table_rows(devices) -> list[dict]:
    return [
        {
            "ID": d.id,
            "Nombre": d.name,
            "Alias": d.alias,
            "Tipo": d.device_type,
            "Fabricante": d.manufacturer or "-",
            "Estado": _STATUS_LABELS.get(d.discovery_status, d.discovery_status),
            "Gestión": d.management_status,
            "Origen": d.source,
            "Primera vez visto": format_datetime(d.first_seen_at),
            "Última vez visto": format_datetime(d.last_seen_at),
        }
        for d in devices
    ]


st.title(f"{ICONS['discovery']} Descubrimiento e inventario")
st.write(
    "Descubrimiento automático **simulado** de dispositivos del laboratorio (spec v0.3.0-dev). "
    "No se realiza ningún escaneo ni conexión real: todo corre sobre fixtures JSON locales. "
    "Un dispositivo detectado queda **pendiente de aprobación** — nunca se administra automáticamente."
)

(
    tab_summary,
    tab_run,
    tab_pending,
    tab_inventory,
    tab_ignored,
    tab_conflicts,
    tab_manual,
) = st.tabs(
    [
        f"{ICONS['list']} Resumen",
        f"{ICONS['play']} Ejecutar descubrimiento",
        f"{ICONS['pending']} Pendientes",
        f"{ICONS['inventory']} Inventario",
        f"{ICONS['ignore_action']} Ignorados",
        f"{ICONS['conflict']} Conflictos y duplicados",
        f"{ICONS['manual']} Registro manual",
    ]
)

inventory_service = get_inventory_service()
inventory_repository = get_inventory_device_repository()
onboarding_service = get_onboarding_service()


with tab_summary:
    summary = inventory_service.summary()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"{ICONS['inventory']} Total en inventario", summary["total"])
    col2.metric(f"{ICONS['pending']} Pendientes de aprobación", summary["pending_approval"])
    col3.metric(f"{ICONS['approve']} Administrados", summary["approved"])
    col4.metric(f"{ICONS['ignore_action']} Ignorados", summary["ignored"])

    col1, col2, col3 = st.columns(3)
    col1.metric(f"{ICONS['warning']} Sin observar (stale)", summary["stale"])
    col2.metric(f"{ICONS['conflict']} Conflictos de identidad", summary["identity_conflicts"])
    col3.metric(f"{ICONS['merge']} Posibles duplicados", summary["possible_duplicate_pairs"])

    st.caption(f"{ICONS['result']} Observaciones registradas en total: {summary['observations_total']}")

    st.divider()
    st.markdown(f"**{ICONS['clock']} Marcar dispositivos sin observar recientemente como 'stale'**")
    st.caption(
        "Un dispositivo administrado o pendiente que no vuelve a aparecer en ningún descubrimiento "
        "durante 7 días pasa a estado `STALE`."
    )
    if st.button(f"{ICONS['clock']} Revisar dispositivos inactivos"):
        changed = inventory_service.mark_stale()
        st.success(f"{changed} dispositivo(s) marcados como `STALE`." if changed else "Ningún dispositivo cambió de estado.")
        st.rerun()


with tab_run:
    st.subheader(f"{ICONS['play']} Ejecutar descubrimiento")
    source = st.radio(
        "Fuente",
        ["Descubrimiento simulado", "Descubrimiento local Windows"],
        horizontal=True,
    )

    if source == "Descubrimiento simulado":
        fixtures = list_available_fixtures()
        if not fixtures:
            st.warning("No hay fixtures de descubrimiento disponibles en `discovery/collectors/fixtures/`.")
        else:
            fixture_names = {f.name: f for f in fixtures}
            selected_fixture_name = st.selectbox("Fixture de red simulada", list(fixture_names.keys()))

            if st.button(f"{ICONS['play']} Ejecutar descubrimiento simulado", type="primary"):
                with st.spinner("Recolectando, normalizando y correlacionando observaciones…"):
                    collector = SimulatedDiscoveryCollector(fixture_names[selected_fixture_name])
                    evidence = get_discovery_service().run(collector, fixture_name=selected_fixture_name)
                _render_run_result(evidence)

    else:
        discovery_config = load_discovery_config()
        st.caption(
            "Recolecta vecinos IPv4/IPv6 reales de la interfaz Ethernet configurada, vía PowerShell "
            "(`Get-NetNeighbor`). Nunca inicia sesión SSH, nunca modifica un router, nunca hace un "
            "barrido de la subred completa."
        )

        interface_info = None
        interface_error = None
        if discovery_config.interface_index is None:
            interface_error = "No hay `discovery.interface_index` configurado en `config/settings.yaml`."
        else:
            try:
                interface_info = get_net_ip_configuration(
                    discovery_config.interface_index, discovery_config.command_timeout_seconds
                )
            except Exception:
                interface_error = (
                    "No fue posible consultar la interfaz de red. Verifica que PowerShell esté disponible "
                    "y que la sesión tenga permisos suficientes."
                )

        if interface_error:
            st.error(interface_error)
        elif interface_info is None:
            st.warning(f"No se encontró la interfaz con índice {discovery_config.interface_index}.")
        else:
            alias_matches = str(interface_info.get("InterfaceAlias", "")).lower() == discovery_config.interface_alias.lower()
            if not alias_matches:
                st.warning(
                    f"El índice configurado ya no corresponde al alias '{discovery_config.interface_alias}' "
                    f"(ahora es '{interface_info.get('InterfaceAlias')}'). Actualiza "
                    f"`discovery.interface_index` en `config/settings.yaml` antes de continuar."
                )
            if str(interface_info.get("Status", "")).lower() != "up":
                st.warning("La interfaz configurada no está activa (`Status` distinto de `Up`).")
            if not interface_info.get("IPv4Gateway"):
                st.warning("La interfaz no reporta gateway IPv4 — puede no estar conectada a la red del laboratorio.")

            col1, col2, col3 = st.columns(3)
            col1.metric("Alias", interface_info.get("InterfaceAlias", "-"))
            col2.metric("Índice", interface_info.get("InterfaceIndex", "-"))
            col3.metric("Estado", interface_info.get("Status", "-"))
            col1, col2, col3 = st.columns(3)
            col1.metric("IPv4", interface_info.get("IPv4Address") or "-")
            col2.metric("Gateway", interface_info.get("IPv4Gateway") or "-")
            col3.metric("MAC", interface_info.get("MacAddress") or "-")
            st.caption(
                f"Adaptador: {interface_info.get('InterfaceDescription', '-')} · "
                f"IPv6: {interface_info.get('IPv6Address') or '-'} · "
                f"DNS: {interface_info.get('DNSServer') or '-'}"
            )

        allow_enrichment = st.checkbox(
            "Permitir enriquecimiento activo (sondas de puerto, cabeceras HTTP, banner SSH)",
            value=discovery_config.allow_active_enrichment,
            help=(
                "Necesario para clasificar el tipo de dispositivo (OpenWrt/Morse Micro/BeaglePlay). "
                "Solo consulta puertos ya permitidos en `config/settings.yaml`; nunca abre una sesión SSH."
            ),
        )

        run_disabled = interface_info is None or interface_error is not None
        if st.button(f"{ICONS['play']} Ejecutar descubrimiento local", type="primary", disabled=run_disabled):
            run_config = discovery_config.model_copy(update={"allow_active_enrichment": allow_enrichment})
            evidence = None
            with st.spinner("Recolectando vecinos IPv4/IPv6, filtrando y clasificando…"):
                collector = WindowsNeighborCollector(run_config)
                try:
                    evidence = get_discovery_service().run(collector, fixture_name=None)
                except RouterAppError as exc:
                    st.error(exc.friendly_message)
                except Exception:
                    st.error("Ocurrió un error inesperado al ejecutar el descubrimiento local.")
            if evidence is not None:
                _render_run_result(evidence)


with tab_pending:
    st.subheader(f"{ICONS['pending']} Dispositivos pendientes de aprobación")
    pending = inventory_service.list_pending()
    if not pending:
        st.info("No hay dispositivos pendientes de aprobación.")
    else:
        st.dataframe(_device_table_rows(pending), use_container_width=True, hide_index=True)

        options = {f"{d.name} (#{d.id})": d for d in pending}
        selected_label = st.selectbox("Selecciona un dispositivo pendiente", list(options.keys()))
        selected = options[selected_label]

        detail = inventory_service.device_detail(selected.id)
        with st.expander(f"{ICONS['search']} Detalle de {selected.name}", expanded=True):
            st.write(f"**Tipo:** {selected.device_type} · **Fabricante:** {selected.manufacturer or '-'}")
            st.write(f"**Origen:** {selected.source}")
            st.markdown(f"**{ICONS['link']} Identificadores**")
            st.dataframe(
                [
                    {"Tipo": i.identifier_type, "Valor": i.normalized_value, "Confianza": round(i.confidence, 2)}
                    for i in detail["identifiers"]
                ],
                use_container_width=True,
                hide_index=True,
            )
            if detail["addresses"]:
                st.markdown(f"**{ICONS['check_wan']} Direcciones**")
                st.dataframe(
                    [
                        {"Dirección": a.address, "Familia": a.address_family, "Vigente": a.is_current}
                        for a in detail["addresses"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        col_approve, col_edit, col_ignore = st.columns(3)
        with col_approve:
            if st.button(f"{ICONS['approve']} Aprobar tal cual", key=f"approve_{selected.id}"):
                onboarding_service.approve(selected.id)
                st.success(f"{selected.name} aprobado y movido al inventario administrado.")
                st.rerun()
        with col_ignore:
            if st.button(f"{ICONS['ignore_action']} Ignorar", key=f"ignore_{selected.id}"):
                onboarding_service.ignore(selected.id)
                st.success(f"{selected.name} marcado como ignorado.")
                st.rerun()

        with col_edit:
            with st.popover(f"{ICONS['edit']} Editar y aprobar"):
                with st.form(f"edit_approve_{selected.id}"):
                    new_name = st.text_input("Nombre", value=selected.name)
                    new_alias = st.text_input("Alias", value=selected.alias)
                    new_type = st.selectbox(
                        "Tipo de dispositivo",
                        [t.value for t in DeviceType],
                        index=[t.value for t in DeviceType].index(selected.device_type),
                    )
                    if st.form_submit_button(f"{ICONS['approve']} Guardar y aprobar"):
                        onboarding_service.edit_and_approve(
                            selected.id, name=new_name, alias=new_alias, device_type=DeviceType(new_type)
                        )
                        st.success(f"{new_name} editado y aprobado.")
                        st.rerun()


with tab_inventory:
    st.subheader(f"{ICONS['inventory']} Inventario completo")
    all_devices = inventory_service.list_all()
    if not all_devices:
        st.info("Todavía no hay dispositivos en el inventario. Registra uno manualmente o ejecuta un descubrimiento.")
    else:
        status_options = ["Todos"] + sorted({d.discovery_status for d in all_devices})
        status_filter = st.selectbox("Filtrar por estado", status_options, key="inventory_status_filter")
        filtered = all_devices if status_filter == "Todos" else [d for d in all_devices if d.discovery_status == status_filter]
        st.dataframe(_device_table_rows(filtered), use_container_width=True, hide_index=True)


with tab_ignored:
    st.subheader(f"{ICONS['ignore_action']} Dispositivos ignorados")
    ignored = inventory_service.list_ignored()
    if not ignored:
        st.info("No hay dispositivos ignorados.")
    else:
        st.dataframe(_device_table_rows(ignored), use_container_width=True, hide_index=True)
        options = {f"{d.name} (#{d.id})": d for d in ignored}
        selected_label = st.selectbox("Selecciona un dispositivo ignorado", list(options.keys()))
        selected = options[selected_label]
        if st.button(f"{ICONS['restore']} Restaurar", key=f"restore_{selected.id}"):
            onboarding_service.restore(selected.id)
            st.success(f"{selected.name} restaurado.")
            st.rerun()


with tab_conflicts:
    st.subheader(f"{ICONS['conflict']} Conflictos de identidad")
    conflicts = inventory_service.list_identity_conflicts()
    if not conflicts:
        st.info("No hay conflictos de identidad registrados.")
    else:
        st.dataframe(
            [
                {
                    "Fecha": format_datetime(c.observed_at),
                    "Tipo": c.observation_type,
                    "Origen": c.source,
                    "Confianza": round(c.confidence, 2),
                }
                for c in conflicts
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Un conflicto ocurre cuando dos identificadores fuertes de la misma observación "
            "(por ejemplo MAC y agent_id) apuntan a dispositivos distintos ya registrados. "
            "Revisa el detalle en Historial/evidencia y resuelve manualmente con una fusión si aplica."
        )

    st.divider()
    st.subheader(f"{ICONS['merge']} Posibles duplicados")
    duplicates = inventory_service.list_possible_duplicates()
    if not duplicates:
        st.info("No se detectaron posibles duplicados en el inventario.")
    else:
        for candidate in duplicates:
            device_a = inventory_repository.get_by_id(candidate.device_a_id)
            device_b = inventory_repository.get_by_id(candidate.device_b_id)
            if device_a is None or device_b is None:
                continue
            with st.expander(
                f"{device_a.name} (#{device_a.id}) ↔ {device_b.name} (#{device_b.id}) "
                f"— confianza {candidate.confidence:.2f}"
            ):
                st.write(f"**Identificadores compartidos:** {', '.join(candidate.shared_identifier_types)}")
                st.write(f"**{device_a.name}:** {device_a.discovery_status} · última vez visto {format_datetime(device_a.last_seen_at)}")
                st.write(f"**{device_b.name}:** {device_b.discovery_status} · última vez visto {format_datetime(device_b.last_seen_at)}")

                merge_col1, merge_col2 = st.columns(2)
                with merge_col1:
                    direction_a_to_b = st.checkbox(
                        f"Fusionar {device_a.name} → {device_b.name} (se conserva {device_b.name})",
                        key=f"dir_{device_a.id}_{device_b.id}",
                    )
                with merge_col2:
                    confirm_merge = st.checkbox(
                        "Confirmo que deseo fusionar estos dispositivos. Esta acción no se puede deshacer.",
                        key=f"confirm_merge_{device_a.id}_{device_b.id}",
                    )
                if st.button(f"{ICONS['merge']} Fusionar", key=f"merge_btn_{device_a.id}_{device_b.id}", disabled=not confirm_merge):
                    source_id, target_id = (device_a.id, device_b.id) if direction_a_to_b else (device_b.id, device_a.id)
                    try:
                        onboarding_service.merge(source_id, target_id, confirmed=True)
                    except RouterAppError as exc:
                        st.error(exc.friendly_message)
                    else:
                        st.success("Dispositivos fusionados correctamente.")
                        st.rerun()


def _register_manual_device(
    *,
    name: str,
    alias: str,
    device_type: str,
    hostname: str,
    ipv4: str,
    mac: str,
    agent_id: str,
    serial: str,
    thread_ext_address: str,
    manufacturer: str,
    location: str,
    notes: str,
) -> list[str]:
    """Validates and persists a manually-registered device. Returns a list
    of validation error messages (empty means it was saved successfully)."""
    errors: list[str] = []
    if not name.strip():
        errors.append("El nombre es obligatorio.")
    if not alias.strip():
        errors.append("El alias es obligatorio.")
    if not any([hostname, ipv4, mac, agent_id, serial, thread_ext_address]):
        errors.append(
            "Ingresa al menos un identificador (hostname, IPv4, MAC, agent ID, serial o Thread "
            "Extended Address) para poder correlacionar este dispositivo con futuras observaciones."
        )

    normalized: dict[str, str] = {}
    try:
        if hostname:
            normalized["hostname"] = normalize_hostname(hostname)
        if ipv4:
            normalized["ipv4"] = normalize_ipv4(ipv4)
        if mac:
            normalized["mac"] = normalize_mac(mac)
        if thread_ext_address:
            normalized["thread_ext_address"] = normalize_thread_ext_address(thread_ext_address)
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        return errors

    inventory_repository = get_inventory_device_repository()
    identifier_repository = get_identifier_repository()
    now = datetime.now().astimezone()

    record = inventory_repository.create(
        name=name.strip(),
        alias=alias.strip(),
        device_type=DeviceType(device_type),
        management_status=DeviceManagementStatus.UNMANAGED,
        discovery_status=DeviceDiscoveryStatus.APPROVED,
        source="manual",
        created_manually=True,
        manufacturer=manufacturer or None,
        metadata={"location": location, "notes": notes} if (location or notes) else None,
        seen_at=now,
    )

    identifier_inputs = [
        (IdentifierType.HOSTNAME, hostname, normalized.get("hostname"), 1.0),
        (IdentifierType.IPV4, ipv4, normalized.get("ipv4"), 0.6),
        (IdentifierType.MAC, mac, normalized.get("mac"), 1.0),
        (IdentifierType.AGENT_ID, agent_id, agent_id.strip() if agent_id else None, 1.0),
        (IdentifierType.SERIAL, serial, serial.strip().upper() if serial else None, 1.0),
        (IdentifierType.THREAD_EXT_ADDRESS, thread_ext_address, normalized.get("thread_ext_address"), 1.0),
    ]
    for identifier_type, raw_value, normalized_value, confidence in identifier_inputs:
        if not raw_value or not normalized_value:
            continue
        identifier_repository.upsert(
            device_id=record.id,
            identifier_type=identifier_type,
            identifier_value=raw_value,
            normalized_value=normalized_value,
            confidence=confidence,
            source="manual",
            seen_at=now,
        )

    if "ipv4" in normalized:
        get_address_repository().upsert(
            device_id=record.id,
            address=normalized["ipv4"],
            address_family=AddressFamily.IPV4,
            scope=AddressScope.GLOBAL,
            source="manual",
            seen_at=now,
        )

    return []


with tab_manual:
    st.subheader(f"{ICONS['manual']} Registro manual de dispositivo")
    st.write(
        "Registra un dispositivo directamente en el inventario, sin pasar por el flujo de "
        "descubrimiento. Queda aprobado de inmediato."
    )
    with st.form("manual_device_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Nombre")
            alias = st.text_input("Alias")
            device_type = st.selectbox("Tipo de dispositivo", [t.value for t in DeviceType])
            hostname = st.text_input("Hostname (opcional)")
            ipv4 = st.text_input("IPv4 (opcional)")
        with col2:
            mac = st.text_input("MAC (opcional)")
            agent_id = st.text_input("Agent ID (opcional)")
            serial = st.text_input("Serial (opcional)")
            thread_ext_address = st.text_input("Thread Extended Address (opcional)")
            manufacturer = st.text_input("Fabricante (opcional)")
        location = st.text_input("Ubicación (opcional)")
        notes = st.text_area("Notas (opcional)")
        submitted = st.form_submit_button(f"{ICONS['add']} Registrar dispositivo")

    if submitted:
        validation_errors = _register_manual_device(
            name=name,
            alias=alias,
            device_type=device_type,
            hostname=hostname,
            ipv4=ipv4,
            mac=mac,
            agent_id=agent_id,
            serial=serial,
            thread_ext_address=thread_ext_address,
            manufacturer=manufacturer,
            location=location,
            notes=notes,
        )
        if validation_errors:
            for error in validation_errors:
                st.error(error)
        else:
            st.success(f"Dispositivo **{name}** registrado y aprobado.")
            st.rerun()
