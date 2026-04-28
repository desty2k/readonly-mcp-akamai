"""Tests for utility tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from helpers import extract_tools


class TestListGroups:
    async def test_returns_groups(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "groups": {
                    "items": [
                        {
                            "groupId": "grp_1",
                            "groupName": "Root Group",
                            "parentGroupId": None,
                            "contractIds": ["ctr_1", "ctr_2"],
                            "extraField": "stripped",
                        },
                        {
                            "groupId": "grp_2",
                            "groupName": "Child Group",
                            "parentGroupId": "grp_1",
                            "contractIds": ["ctr_1"],
                        },
                    ]
                }
            }
        )

        from mcp_akamai.tools import utility

        tools = extract_tools(utility)
        results = await tools["list_groups"](mock_ctx)

        assert len(results) == 2
        assert results[0]["groupName"] == "Root Group"
        assert results[1]["parentGroupId"] == "grp_1"
        assert "extraField" not in results[0]

    async def test_empty_groups(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"groups": {"items": []}})

        from mcp_akamai.tools import utility

        tools = extract_tools(utility)
        results = await tools["list_groups"](mock_ctx)
        assert results == []


class TestListCpCodes:
    async def test_returns_cp_codes(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "cpcodes": {
                    "items": [
                        {
                            "cpcodeId": "cpc_12345",
                            "cpcodeName": "Main Site",
                            "productIds": ["prd_1"],
                            "createdDate": "2024-01-01T00:00:00Z",
                            "extraField": "stripped",
                        },
                    ]
                }
            }
        )

        from mcp_akamai.tools import utility

        tools = extract_tools(utility)
        results = await tools["list_cp_codes"](mock_ctx, contract_id="ctr_1", group_id="grp_1")

        assert len(results) == 1
        assert results[0]["cpcodeId"] == "cpc_12345"
        assert results[0]["cpcodeName"] == "Main Site"
        assert "extraField" not in results[0]

    async def test_empty_cp_codes(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(return_value={"cpcodes": {"items": []}})

        from mcp_akamai.tools import utility

        tools = extract_tools(utility)
        results = await tools["list_cp_codes"](mock_ctx, contract_id="ctr_1", group_id="grp_1")
        assert results == []


class TestTranslateErrorCode:
    async def test_translates_error(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.post_json = AsyncMock(
            return_value={
                "translatedError": {
                    "httpResponseCode": 503,
                    "timestamp": "2025-01-01T00:00:00Z",
                    "epochTime": 1735689600,
                    "clientIp": "1.2.3.4",
                    "serverIp": "5.6.7.8",
                    "originHostname": "origin.example.com",
                    "originIp": "10.0.0.1",
                    "userAgent": "Mozilla/5.0",
                    "requestMethod": "GET",
                    "reasonForFailure": "Origin server returned 503",
                    "wafDetails": None,
                    "logs": ["Log entry 1", "Log entry 2"],
                }
            }
        )

        from mcp_akamai.tools import utility

        tools = extract_tools(utility)
        result = await tools["translate_error_code"](mock_ctx, error_code="9.6f64d440.1318965461.2f2b078")

        assert result["errorCode"] == "9.6f64d440.1318965461.2f2b078"
        assert result["httpResponseCode"] == 503
        assert result["reasonForFailure"] == "Origin server returned 503"
        assert len(result["logs"]) == 2

    async def test_error_code_passed_to_api(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.post_json = AsyncMock(return_value={"translatedError": {}})

        from mcp_akamai.tools import utility

        tools = extract_tools(utility)
        await tools["translate_error_code"](mock_ctx, error_code="9.abc.123.xyz")

        client.post_json.assert_called_once_with(
            "/edge-diagnostics/v1/error-translator",
            body={"errorCode": "9.abc.123.xyz"},
        )
