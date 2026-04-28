"""Configuration from environment variables."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AkamaiSettings(BaseSettings):
    """Akamai MCP server settings loaded from AKAMAI_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="AKAMAI_")

    host: str
    client_token: str
    client_secret: str = Field(repr=False)
    access_token: str

    transport: Literal["stdio", "http", "sse"] = "stdio"
    http_port: int = 8080

    log_format: Literal["json", "text"] = "json"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    index_refresh_interval: int = 300
