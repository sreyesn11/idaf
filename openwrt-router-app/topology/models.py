from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from diagnostics.enums import DiagnosticState


class TopologyNode(BaseModel):
    id: str
    label: str
    type: str
    state: DiagnosticState
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopologyLink(BaseModel):
    source: str
    target: str
    type: str
    state: DiagnosticState
    metrics: dict[str, Any] = Field(default_factory=dict)


class TopologyGraph(BaseModel):
    nodes: list[TopologyNode]
    links: list[TopologyLink]
