from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from diagnostics.enums import DiagnosticState


class StateChangeEvent(BaseModel):
    """Recorded whenever a new diagnostic changes a device's previously observed state."""

    event_type: str = "state_change"
    target_device_id: str
    from_state: DiagnosticState
    to_state: DiagnosticState
    timestamp: datetime
    source: str = "router_general_health"
