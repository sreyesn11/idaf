from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from discovery.enums import (
    AddressFamily,
    AddressScope,
    CollectorType,
    CorrelationStatus,
    DeviceType,
    IdentifierType,
    ObservationType,
)


class RawDiscoveryObservation(BaseModel):
    """One sighting as produced by a collector, before normalization.

    This is the shape every future real collector (DHCP, mDNS, Thread border
    router, ...) must produce — `discovery_service` never depends on how a
    collector obtained this data.
    """

    collector_id: str
    collector_type: CollectorType
    observed_at: datetime
    observation_type: ObservationType
    source: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ExtractedIdentifier(BaseModel):
    identifier_type: IdentifierType
    value: str
    normalized_value: str
    confidence: float = 1.0


class ExtractedAddress(BaseModel):
    address: str
    address_family: AddressFamily
    scope: AddressScope
    prefix_length: int | None = None
    is_current: bool = True


class NormalizedObservation(BaseModel):
    """A `RawDiscoveryObservation` after validation/canonicalization.

    `normalization_errors` holds per-field problems that were skipped rather
    than accepted silently (spec section 9) — the observation still carries
    whatever *did* normalize successfully.
    """

    observation_type: ObservationType
    collector_id: str
    collector_type: CollectorType
    source: str
    observed_at: datetime
    device_type_hint: DeviceType | None = None
    hostname: str | None = None
    manufacturer_hint: str | None = None
    parent_hostname: str | None = None
    identifiers: list[ExtractedIdentifier] = Field(default_factory=list)
    addresses: list[ExtractedAddress] = Field(default_factory=list)
    normalization_errors: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class IdentityResolution(BaseModel):
    """Outcome of running a `NormalizedObservation` through `DeviceIdentityResolver`."""

    status: CorrelationStatus
    confidence: float
    resolved_device_id: int | None = None
    candidate_device_ids: list[int] = Field(default_factory=list)
    matched_identifier_types: list[IdentifierType] = Field(default_factory=list)
    notes: str | None = None


class DiscoveryRunResultItem(BaseModel):
    observation_type: ObservationType
    source: str
    correlation_status: CorrelationStatus
    confidence: float
    device_id: int | None = None
    device_name: str | None = None
    notes: str | None = None


class DiscoveryRunEvidence(BaseModel):
    """Evidence JSON written after every discovery run (spec section 17)."""

    execution_id: str
    collector: str
    fixture: str | None = None
    started_at: datetime
    finished_at: datetime
    observations_received: int = 0
    observations_normalized: int = 0
    devices_created: int = 0
    devices_updated: int = 0
    possible_duplicates: int = 0
    identity_conflicts: int = 0
    ignored: int = 0
    errors: list[str] = Field(default_factory=list)
    results: list[DiscoveryRunResultItem] = Field(default_factory=list)
    # Populated only for real collectors that expose `last_run_stats` (e.g.
    # WindowsNeighborCollector) — always None for the simulated fixture.
    interface: dict[str, Any] | None = None
    raw_ipv4_neighbors: int | None = None
    raw_ipv6_neighbors: int | None = None
    filtered_entries: int | None = None


class MergePreview(BaseModel):
    """What a merge would do, shown to the user before they confirm it."""

    source_device_id: int
    source_name: str
    target_device_id: int
    target_name: str
    identifiers_to_move: int
    addresses_to_move: int
    interfaces_to_move: int
    observations_to_move: int
