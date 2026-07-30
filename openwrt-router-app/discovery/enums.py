from __future__ import annotations

from enum import Enum


class DeviceDiscoveryStatus(str, Enum):
    """Where a device sits in the discover -> approve pipeline (spec section 4.2)."""

    DISCOVERED = "DISCOVERED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    IGNORED = "IGNORED"
    STALE = "STALE"
    REMOVED = "REMOVED"


class DeviceManagementStatus(str, Enum):
    """Whether IDAF actively manages the device (e.g. can SSH into it) or only observes it."""

    UNMANAGED = "UNMANAGED"
    MANAGED = "MANAGED"


class DeviceType(str, Enum):
    ROUTER = "ROUTER"
    GATEWAY = "GATEWAY"
    OPENWRT_ROUTER = "OPENWRT_ROUTER"
    BORDER_ROUTER = "BORDER_ROUTER"
    SERVER = "SERVER"
    COMPUTER = "COMPUTER"
    RASPBERRY_PI = "RASPBERRY_PI"
    BEAGLEPLAY = "BEAGLEPLAY"
    ESP32 = "ESP32"
    ESP32_C6 = "ESP32_C6"
    IOT_NODE = "IOT_NODE"
    SENSOR = "SENSOR"
    PHONE = "PHONE"
    UNKNOWN = "UNKNOWN"


class IdentifierType(str, Enum):
    MAC = "MAC"
    IPV4 = "IPV4"
    IPV6 = "IPV6"
    HOSTNAME = "HOSTNAME"
    MDNS_NAME = "MDNS_NAME"
    AGENT_ID = "AGENT_ID"
    SERIAL = "SERIAL"
    THREAD_EXT_ADDRESS = "THREAD_EXT_ADDRESS"
    RLOC16 = "RLOC16"


class ObservationType(str, Enum):
    IPV4_NEIGHBOR = "IPV4_NEIGHBOR"
    IPV6_NEIGHBOR = "IPV6_NEIGHBOR"
    DHCP_LEASE = "DHCP_LEASE"
    WIFI_CLIENT = "WIFI_CLIENT"
    MDNS_SERVICE = "MDNS_SERVICE"
    GATEWAY_REPORT = "GATEWAY_REPORT"
    THREAD_NODE_REPORT = "THREAD_NODE_REPORT"


class CorrelationStatus(str, Enum):
    NEW_DEVICE = "NEW_DEVICE"
    MATCHED_DEVICE = "MATCHED_DEVICE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CollectorType(str, Enum):
    SIMULATED_ROUTER = "SIMULATED_ROUTER"
    SIMULATED_DHCP = "SIMULATED_DHCP"
    SIMULATED_WIFI = "SIMULATED_WIFI"
    SIMULATED_MDNS = "SIMULATED_MDNS"
    SIMULATED_THREAD = "SIMULATED_THREAD"


class LinkType(str, Enum):
    ETHERNET = "ETHERNET"
    WIFI = "WIFI"
    SSH = "SSH"
    THREAD = "THREAD"
    UNKNOWN = "UNKNOWN"


class AddressFamily(str, Enum):
    IPV4 = "IPV4"
    IPV6 = "IPV6"


class AddressScope(str, Enum):
    GLOBAL = "GLOBAL"
    UNIQUE_LOCAL = "UNIQUE_LOCAL"
    LINK_LOCAL = "LINK_LOCAL"
    LOOPBACK = "LOOPBACK"
