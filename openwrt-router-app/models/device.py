from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from models.connection import ConnectionConfig, HostKeyPolicy


class DeviceConfig(BaseModel):
    """A saved gateway in the device registry.

    Deliberately has no password field: the password is never persisted,
    it only ever lives in `st.session_state` for the duration of a
    Streamlit session, exactly like the original single-device flow.
    """

    id: int | None = None
    alias: str = Field(..., min_length=1)
    host: str = Field(..., min_length=1)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(..., min_length=1)
    timeout: int = Field(default=10, ge=1, le=120)
    host_key_policy: HostKeyPolicy = HostKeyPolicy.AUTO
    created_at: datetime | None = None

    @field_validator("alias", "host", "username")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("no puede estar vacío")
        return value

    def to_connection_config(self, password: str) -> ConnectionConfig:
        return ConnectionConfig(
            host=self.host,
            port=self.port,
            username=self.username,
            password=password,
            timeout=self.timeout,
            host_key_policy=self.host_key_policy,
        )


@dataclass
class ConnectedDevice:
    """An active, session-only SSH connection to a device.

    Never persisted: it lives only in `st.session_state` for the
    duration of the browser session that created it.
    """

    key: str
    device_id: int | None
    alias: str
    connection: ConnectionConfig
    status: str
    connected_at: datetime
