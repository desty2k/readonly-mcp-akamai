"""Shared fixtures for all tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_akamai.cache import BundleCache
from mcp_akamai.client import AkamaiClient
from mcp_akamai.index import PropertyIndex
from mcp_akamai.server import AppContext
from mcp_akamai.settings import AkamaiSettings


@pytest.fixture
def settings() -> AkamaiSettings:
    return AkamaiSettings(
        host="https://test.akamaiapis.net",
        client_token="test-ct",
        client_secret="test-cs",
        access_token="test-at",
        transport="stdio",
        log_format="text",
        log_level="DEBUG",
    )


@pytest.fixture
def mock_client() -> AkamaiClient:
    """A fully mocked AkamaiClient where .get() and .post_json() are AsyncMocks."""
    client = MagicMock(spec=AkamaiClient)
    client.get = AsyncMock()
    client.get_bytes = AsyncMock()
    client.post_json = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def property_index() -> PropertyIndex:
    return PropertyIndex()


@pytest.fixture
def bundle_cache() -> BundleCache:
    return BundleCache()


@pytest.fixture
def app_context(mock_client: AkamaiClient, settings: AkamaiSettings) -> AppContext:
    return AppContext(
        client=mock_client,
        settings=settings,
        property_index=PropertyIndex(),
        bundle_cache=BundleCache(),
    )


@pytest.fixture
def mock_ctx(app_context: AppContext) -> MagicMock:
    """A mock FastMCP Context with lifespan_context set to app_context."""
    ctx = MagicMock()
    ctx.lifespan_context = app_context
    return ctx


def make_groups_response(groups: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a PAPI groups response."""
    if groups is None:
        groups = [
            {"groupId": "grp_1", "groupName": "Test Group", "contractIds": ["ctr_1"]},
        ]
    return {"groups": {"items": groups}}


def make_properties_response(properties: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Build a PAPI properties response."""
    if properties is None:
        properties = [
            {
                "propertyId": "prp_1",
                "propertyName": "example.com",
                "contractId": "ctr_1",
                "groupId": "grp_1",
                "latestVersion": 3,
                "stagingVersion": 2,
                "productionVersion": 1,
                "assetId": "aid_1",
            },
        ]
    return {"properties": {"items": properties}}
