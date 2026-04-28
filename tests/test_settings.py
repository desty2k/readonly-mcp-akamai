"""Tests for settings validation."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from mcp_akamai.settings import AkamaiSettings


class TestAkamaiSettings:
    def test_loads_from_env(self) -> None:
        env = {
            "AKAMAI_HOST": "test.akamaiapis.net",
            "AKAMAI_CLIENT_TOKEN": "ct-123",
            "AKAMAI_CLIENT_SECRET": "Y3MtMTIz",
            "AKAMAI_ACCESS_TOKEN": "at-123",
        }
        with patch.dict(os.environ, env, clear=False):
            s = AkamaiSettings()  # type: ignore[call-arg]
            assert s.host == "test.akamaiapis.net"
            assert s.client_token == "ct-123"
            assert s.access_token == "at-123"

    def test_defaults(self) -> None:
        env = {
            "AKAMAI_HOST": "test.akamaiapis.net",
            "AKAMAI_CLIENT_TOKEN": "ct",
            "AKAMAI_CLIENT_SECRET": "cs",
            "AKAMAI_ACCESS_TOKEN": "at",
        }
        with patch.dict(os.environ, env, clear=False):
            s = AkamaiSettings()  # type: ignore[call-arg]
            assert s.transport == "stdio"
            assert s.http_port == 8080
            assert s.log_format == "json"
            assert s.log_level == "INFO"
            assert s.index_refresh_interval == 300

    def test_missing_required_field(self) -> None:
        env = {
            "AKAMAI_HOST": "test.akamaiapis.net",
            # Missing client_token, client_secret, access_token
        }
        with patch.dict(os.environ, env, clear=False):
            # Remove potentially set vars
            for key in ["AKAMAI_CLIENT_TOKEN", "AKAMAI_CLIENT_SECRET", "AKAMAI_ACCESS_TOKEN"]:
                os.environ.pop(key, None)
            with pytest.raises(ValidationError):
                AkamaiSettings()  # type: ignore[call-arg]

    def test_secret_hidden_in_repr(self) -> None:
        s = AkamaiSettings(
            host="test.akamaiapis.net",
            client_token="ct",
            client_secret="secret-value",
            access_token="at",
        )
        repr_str = repr(s)
        assert "secret-value" not in repr_str

    def test_custom_values(self) -> None:
        env = {
            "AKAMAI_HOST": "custom.akamaiapis.net",
            "AKAMAI_CLIENT_TOKEN": "ct",
            "AKAMAI_CLIENT_SECRET": "cs",
            "AKAMAI_ACCESS_TOKEN": "at",
            "AKAMAI_TRANSPORT": "http",
            "AKAMAI_HTTP_PORT": "9090",
            "AKAMAI_LOG_FORMAT": "text",
            "AKAMAI_LOG_LEVEL": "DEBUG",
            "AKAMAI_INDEX_REFRESH_INTERVAL": "60",
        }
        with patch.dict(os.environ, env, clear=False):
            s = AkamaiSettings()  # type: ignore[call-arg]
            assert s.transport == "http"
            assert s.http_port == 9090
            assert s.log_format == "text"
            assert s.log_level == "DEBUG"
            assert s.index_refresh_interval == 60
