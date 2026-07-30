from __future__ import annotations

from typing import Protocol

from discovery.enums import CollectorType
from discovery.models import RawDiscoveryObservation


class DiscoveryCollector(Protocol):
    """Anything that can produce raw discovery observations.

    The domain (normalization, correlation, services) only ever depends on
    this interface — never on SSH, Linksys, or OpenWrt specifics — so a real
    collector (DHCP lease reader, mDNS browser, Thread border-router agent,
    ...) can be dropped in later without touching the rest of the pipeline.
    """

    collector_type: CollectorType

    def collect(self) -> list[RawDiscoveryObservation]: ...
