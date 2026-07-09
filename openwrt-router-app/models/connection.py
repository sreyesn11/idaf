from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, SecretStr, field_validator


class HostKeyPolicy(str, Enum):
    AUTO = "auto"
    REJECT = "reject"


class ConnectionConfig(BaseModel):
    """SSH connection parameters for the router.

    The password is wrapped in SecretStr so it never shows up in logs,
    reprs or accidental str() conversions. Callers that need the raw
    value must call `password.get_secret_value()` explicitly.
    """

    host: str = Field(..., min_length=1)
    port: int = Field(default=22, ge=1, le=65535)
    username: str = Field(..., min_length=1)
    password: SecretStr
    timeout: int = Field(default=10, ge=1, le=120)
    host_key_policy: HostKeyPolicy = HostKeyPolicy.AUTO

    @field_validator("host", "username")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("no puede estar vacío")
        return value

    def __repr__(self) -> str:
        return (
            f"ConnectionConfig(host={self.host!r}, port={self.port}, "
            f"username={self.username!r}, timeout={self.timeout})"
        )
