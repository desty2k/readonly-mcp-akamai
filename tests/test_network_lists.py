"""Tests for network list tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from helpers import extract_tools


class TestSearchNetworkLists:
    async def test_returns_lists(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "networkLists": [
                    {
                        "uniqueId": "12345_BLOCKLIST",
                        "name": "Bad IPs",
                        "type": "IP",
                        "elementCount": 150,
                        "syncPoint": 10,
                        "description": "Known bad actors",
                        "extraField": "stripped",
                    },
                    {
                        "uniqueId": "67890_GEOBLOCK",
                        "name": "Blocked Countries",
                        "type": "GEO",
                        "elementCount": 5,
                        "syncPoint": 3,
                        "description": "",
                    },
                ]
            }
        )

        from mcp_akamai.tools import network_lists

        tools = extract_tools(network_lists)
        results = await tools["search_network_lists"](mock_ctx)

        assert len(results) == 2
        assert results[0]["uniqueId"] == "12345_BLOCKLIST"
        assert results[0]["type"] == "IP"
        assert "extraField" not in results[0]

    async def test_search_filter(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"networkLists": []})

        from mcp_akamai.tools import network_lists

        tools = extract_tools(network_lists)
        await tools["search_network_lists"](mock_ctx, search="block")

        args, kwargs = client.get.call_args
        params = kwargs.get("params", {})
        assert params.get("search") == "block"

    async def test_type_filter(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"networkLists": []})

        from mcp_akamai.tools import network_lists

        tools = extract_tools(network_lists)
        await tools["search_network_lists"](mock_ctx, list_type="GEO")

        args, kwargs = client.get.call_args
        params = kwargs.get("params", {})
        assert params.get("listType") == "GEO"

    async def test_empty_results(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"networkLists": []})

        from mcp_akamai.tools import network_lists

        tools = extract_tools(network_lists)
        results = await tools["search_network_lists"](mock_ctx)
        assert results == []


class TestGetNetworkList:
    async def test_returns_full_list(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "uniqueId": "12345_BLOCKLIST",
                "name": "Bad IPs",
                "type": "IP",
                "elementCount": 3,
                "description": "Known bad actors",
                "list": ["1.2.3.4", "10.0.0.0/8", "192.168.1.0/24"],
                "links": {"should": "be stripped"},
            }
        )

        from mcp_akamai.tools import network_lists

        tools = extract_tools(network_lists)
        result = await tools["get_network_list"](mock_ctx, unique_id="12345_BLOCKLIST")

        assert result["uniqueId"] == "12345_BLOCKLIST"
        assert result["list"] == ["1.2.3.4", "10.0.0.0/8", "192.168.1.0/24"]
        assert result["elementCount"] == 3
        assert "links" not in result
