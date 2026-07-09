from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ParserType(str, Enum):
    JSON = "json"
    TEXT = "text"
    LINES = "lines"
    UPTIME = "uptime"
    FREE = "free"
    DF = "df"


class CommandDefinition(BaseModel):
    """A single allow-listed command, as declared in config/commands.yaml."""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str = ""
    command: str = Field(..., min_length=1)
    parser: ParserType
    category: str = Field(..., min_length=1)
    timeout: int = Field(default=10, ge=1, le=300)
    enabled: bool = True
