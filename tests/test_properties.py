"""Tests for property tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from helpers import extract_tools

from mcp_akamai.index import PropertyEntry
from mcp_akamai.server import AppContext
from mcp_akamai.tools.properties import _slim_rules


@pytest.fixture
def ctx_with_index(app_context: AppContext) -> MagicMock:
    """Context with a populated property index."""
    app_context.property_index._entries = [
        PropertyEntry("prp_1", "www.example.com", "ctr_1", "grp_1", 5, 4, 3, "aid_1"),
        PropertyEntry("prp_2", "api.example.com", "ctr_1", "grp_1", 2, 2, 1, "aid_2"),
    ]
    app_context.property_index._names = [e.property_name for e in app_context.property_index._entries]
    app_context.property_index._loaded = True

    ctx = MagicMock()
    ctx.lifespan_context = app_context
    return ctx


class TestSearchProperties:
    async def test_search_returns_matches(self, ctx_with_index: MagicMock) -> None:
        from mcp_akamai.tools import properties

        tools = extract_tools(properties)
        results = await tools["search_properties"](ctx_with_index, query="www", limit=10)
        assert len(results) >= 1
        assert results[0]["propertyName"] == "www.example.com"

    async def test_search_empty_query(self, ctx_with_index: MagicMock) -> None:
        from mcp_akamai.tools import properties

        tools = extract_tools(properties)
        results = await tools["search_properties"](ctx_with_index, query="", limit=10)
        assert isinstance(results, list)

    async def test_search_limit_clamped(self, ctx_with_index: MagicMock) -> None:
        from mcp_akamai.tools import properties

        tools = extract_tools(properties)
        results = await tools["search_properties"](ctx_with_index, query="example", limit=100)
        # Limit is clamped to 50
        assert isinstance(results, list)


class TestGetPropertyDetails:
    async def test_returns_shaped_response(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            side_effect=[
                {
                    "properties": {
                        "items": [
                            {
                                "propertyId": "prp_1",
                                "propertyName": "www.example.com",
                                "contractId": "ctr_1",
                                "groupId": "grp_1",
                                "latestVersion": 3,
                                "stagingVersion": 2,
                                "productionVersion": 1,
                                "note": "Main site",
                                "internalField": "should be stripped",
                            }
                        ]
                    }
                },
                {
                    "hostnames": {
                        "items": [
                            {
                                "cnameFrom": "www.example.com",
                                "cnameTo": "www.example.com.edgesuite.net",
                                "cnameType": "EDGE_HOSTNAME",
                                "extra_field": "should be stripped",
                            }
                        ]
                    }
                },
            ]
        )

        from mcp_akamai.tools import properties

        tools = extract_tools(properties)
        result = await tools["get_property_details"](
            mock_ctx, property_id="prp_1", contract_id="ctr_1", group_id="grp_1"
        )

        assert result["propertyId"] == "prp_1"
        assert result["propertyName"] == "www.example.com"
        assert result["latestVersion"] == 3
        assert result["stagingVersion"] == 2
        assert result["productionVersion"] == 1
        assert result["note"] == "Main site"
        assert len(result["hostnames"]) == 1
        assert result["hostnames"][0]["cnameFrom"] == "www.example.com"
        # Verify extra fields are stripped
        assert "extra_field" not in result["hostnames"][0]
        assert "internalField" not in result

    async def test_empty_hostnames(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            side_effect=[
                {"properties": {"items": [{"propertyId": "prp_1", "latestVersion": 1}]}},
                {"hostnames": {"items": []}},
            ]
        )

        from mcp_akamai.tools import properties

        tools = extract_tools(properties)
        result = await tools["get_property_details"](
            mock_ctx, property_id="prp_1", contract_id="ctr_1", group_id="grp_1"
        )
        assert result["hostnames"] == []


class TestGetPropertyRules:
    async def test_returns_slimmed_rules(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "ruleFormat": "v2024-01-09",
                "rules": {
                    "name": "default",
                    "uuid": "should-be-stripped",
                    "behaviors": [{"name": "origin", "options": {"hostname": "origin.example.com"}, "uuid": "b-1"}],
                    "children": [],
                },
            }
        )

        from mcp_akamai.tools import properties

        tools = extract_tools(properties)
        result = await tools["get_property_rules"](
            mock_ctx, property_id="prp_1", version=3, contract_id="ctr_1", group_id="grp_1"
        )

        assert result["propertyId"] == "prp_1"
        assert result["version"] == 3
        assert result["ruleFormat"] == "v2024-01-09"
        assert "uuid" not in result["rules"]
        assert result["rules"]["behaviors"][0]["name"] == "origin"


class TestGetPropertyActivations:
    async def test_returns_shaped_activations(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "activations": {
                    "items": [
                        {
                            "activationId": "atv_1",
                            "propertyVersion": 3,
                            "network": "PRODUCTION",
                            "activationType": "ACTIVATE",
                            "status": "ACTIVE",
                            "submitDate": "2025-01-01T00:00:00Z",
                            "updateDate": "2025-01-01T00:05:00Z",
                            "note": "Deploy v3",
                            "notifyEmails": ["ops@example.com"],
                            "internalField": "should not appear",
                        }
                    ]
                }
            }
        )

        from mcp_akamai.tools import properties

        tools = extract_tools(properties)
        result = await tools["get_property_activations"](
            mock_ctx, property_id="prp_1", contract_id="ctr_1", group_id="grp_1"
        )

        assert len(result) == 1
        assert result[0]["activationId"] == "atv_1"
        assert result[0]["network"] == "PRODUCTION"
        assert result[0]["status"] == "ACTIVE"
        assert "internalField" not in result[0]

    async def test_empty_activations(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"activations": {"items": []}})

        from mcp_akamai.tools import properties

        tools = extract_tools(properties)
        result = await tools["get_property_activations"](
            mock_ctx, property_id="prp_1", contract_id="ctr_1", group_id="grp_1"
        )
        assert result == []


class TestSlimRules:
    def test_strips_metadata(self) -> None:
        rules = {
            "name": "default",
            "uuid": "abc-123",
            "behaviors": [{"name": "caching", "options": {"ttl": "7d"}, "uuid": "b-1", "locked": False}],
            "criteria": [{"name": "path", "options": {"values": ["/api/*"]}, "uuid": "c-1"}],
            "children": [
                {
                    "name": "Images",
                    "behaviors": [{"name": "caching", "options": {"ttl": "30d"}, "uuid": "b-2"}],
                    "criteria": [],
                    "children": [],
                }
            ],
            "comments": "Main rule",
        }

        result = _slim_rules(rules)

        assert result["name"] == "default"
        assert "uuid" not in result
        assert result["behaviors"][0]["name"] == "caching"
        assert "uuid" not in result["behaviors"][0]
        assert result["comments"] == "Main rule"
        assert len(result["children"]) == 1
        assert result["children"][0]["name"] == "Images"

    def test_empty_children_omitted(self) -> None:
        rules = {"name": "simple", "behaviors": [], "criteria": []}
        result = _slim_rules(rules)
        assert "children" not in result

    def test_empty_behaviors_kept(self) -> None:
        rules = {"name": "test"}
        result = _slim_rules(rules)
        assert result == {"name": "test"}
