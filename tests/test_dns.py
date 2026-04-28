"""Tests for DNS tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from helpers import extract_tools


class TestListDnsZones:
    async def test_returns_zones(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "zones": [
                    {
                        "zone": "example.com",
                        "type": "PRIMARY",
                        "comment": "Main zone",
                        "activationState": "ACTIVE",
                        "extraField": "stripped",
                    },
                    {
                        "zone": "example.org",
                        "type": "SECONDARY",
                        "comment": "",
                        "activationState": "ACTIVE",
                    },
                ]
            }
        )

        from mcp_akamai.tools import dns

        tools = extract_tools(dns)
        results = await tools["list_dns_zones"](mock_ctx)

        assert len(results) == 2
        assert results[0]["zone"] == "example.com"
        assert results[0]["type"] == "PRIMARY"
        assert "extraField" not in results[0]

    async def test_empty_zones(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"zones": []})

        from mcp_akamai.tools import dns

        tools = extract_tools(dns)
        results = await tools["list_dns_zones"](mock_ctx)
        assert results == []

    async def test_search_filter(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"zones": []})

        from mcp_akamai.tools import dns

        tools = extract_tools(dns)
        await tools["list_dns_zones"](mock_ctx, search="example")

        client.get.assert_called_once()
        args, kwargs = client.get.call_args
        params = kwargs.get("params", {})
        assert params.get("search") == "example"

    async def test_zone_type_filter(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"zones": []})

        from mcp_akamai.tools import dns

        tools = extract_tools(dns)
        await tools["list_dns_zones"](mock_ctx, zone_type="PRIMARY")

        args, kwargs = client.get.call_args
        params = kwargs.get("params", {})
        assert params.get("types") == "PRIMARY"


class TestSearchDnsRecords:
    async def test_returns_records(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "recordsets": [
                    {
                        "name": "www.example.com",
                        "type": "CNAME",
                        "ttl": 300,
                        "rdata": ["www.example.com.edgesuite.net."],
                    },
                    {
                        "name": "example.com",
                        "type": "A",
                        "ttl": 60,
                        "rdata": ["1.2.3.4"],
                    },
                ]
            }
        )

        from mcp_akamai.tools import dns

        tools = extract_tools(dns)
        results = await tools["search_dns_records"](mock_ctx, zone="example.com")

        assert len(results) == 2
        assert results[0]["name"] == "www.example.com"
        assert results[0]["type"] == "CNAME"
        assert results[0]["rdata"] == ["www.example.com.edgesuite.net."]

    async def test_record_type_filter(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"recordsets": []})

        from mcp_akamai.tools import dns

        tools = extract_tools(dns)
        await tools["search_dns_records"](mock_ctx, zone="example.com", record_type="CNAME")

        args, kwargs = client.get.call_args
        params = kwargs.get("params", {})
        assert params.get("types") == "CNAME"

    async def test_search_filter(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"recordsets": []})

        from mcp_akamai.tools import dns

        tools = extract_tools(dns)
        await tools["search_dns_records"](mock_ctx, zone="example.com", search="www")

        args, kwargs = client.get.call_args
        params = kwargs.get("params", {})
        assert params.get("search") == "www"
