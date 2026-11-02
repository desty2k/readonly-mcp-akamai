"""Tests for server construction and the entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp_akamai import __version__
from mcp_akamai.__main__ import is_loopback, main
from mcp_akamai.server import create_server
from mcp_akamai.settings import AkamaiSettings


def _settings(**kwargs: object) -> AkamaiSettings:
    return AkamaiSettings(
        host="test.akamaiapis.net",
        client_token="ct",
        client_secret="cs",
        access_token="at",
        **kwargs,  # type: ignore[arg-type]
    )


def test_server_reports_package_version() -> None:
    server = create_server(_settings())
    assert server.version == __version__


async def test_server_registers_sixteen_tools() -> None:
    tools = await create_server(_settings()).list_tools()
    assert len(tools) == 16


async def test_every_tool_is_annotated_read_only() -> None:
    tools = await create_server(_settings()).list_tools()
    for tool in tools:
        assert tool.annotations is not None, tool.name
        assert tool.annotations.readOnlyHint is True, tool.name
        assert tool.annotations.destructiveHint is False, tool.name


def test_http_host_defaults_to_loopback() -> None:
    assert _settings().http_host == "127.0.0.1"


@pytest.mark.parametrize(
    ("host", "expected"),
    [("127.0.0.1", True), ("::1", True), ("localhost", True), ("0.0.0.0", False), ("10.0.0.5", False)],
)
def test_is_loopback(host: str, expected: bool) -> None:
    assert is_loopback(host) is expected


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_http_transports_bind_the_configured_host(transport: str) -> None:
    server = MagicMock()
    with (
        patch("mcp_akamai.__main__.AkamaiSettings", return_value=_settings(transport=transport, log_format="text")),
        patch("mcp_akamai.server.create_server", return_value=server),
    ):
        main()
    assert server.run.call_args.kwargs["host"] == "127.0.0.1"
