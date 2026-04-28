"""Utility tools — groups, CP codes, and error translation."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_groups(
        ctx: Context,
    ) -> list[dict[str, Any]]:
        """List account groups in the Akamai hierarchy. Returns group names,
        IDs, parent relationships, and associated contract IDs.

        Example questions:
        - "What groups exist in the Akamai account?"
        - "Show me the account structure"
        - "Which contracts are associated with each group?"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get("/papi/v1/groups")
        groups = data.get("groups", {}).get("items", [])

        results = []
        for g in groups:
            results.append(
                {
                    "groupId": g.get("groupId"),
                    "groupName": g.get("groupName"),
                    "parentGroupId": g.get("parentGroupId"),
                    "contractIds": g.get("contractIds", []),
                }
            )

        logger.info("list_groups count=%d", len(results))
        return results

    @mcp.tool()
    async def list_cp_codes(
        ctx: Context,
        contract_id: Annotated[str, "Contract ID (e.g., ctr_1-AB123)"],
        group_id: Annotated[str, "Group ID (e.g., grp_12345)"],
    ) -> list[dict[str, Any]]:
        """List CP codes for a contract and group. CP codes are numeric
        identifiers used for billing, reporting, and content segmentation.

        Example questions:
        - "What CP codes are available for this contract?"
        - "Find the CP code for the main website"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(
            "/papi/v1/cpcodes",
            params={"contractId": contract_id, "groupId": group_id},
        )
        cpcodes = data.get("cpcodes", {}).get("items", [])

        results = []
        for cp in cpcodes:
            results.append(
                {
                    "cpcodeId": cp.get("cpcodeId"),
                    "cpcodeName": cp.get("cpcodeName"),
                    "productIds": cp.get("productIds", []),
                    "createdDate": cp.get("createdDate"),
                }
            )

        logger.info("list_cp_codes contract_id=%s group_id=%s count=%d", contract_id, group_id, len(results))
        return results

    @mcp.tool()
    async def translate_error_code(
        ctx: Context,
        error_code: Annotated[str, "Akamai reference error code (e.g., 9.6f64d440.1318965461.2f2b078)"],
    ) -> dict[str, Any]:
        """Translate an Akamai error reference code into human-readable details.
        Returns HTTP response code, client/server IPs, origin info, failure
        reason, and WAF details.

        Example questions:
        - "What does error 9.6f64d440.1318965461.2f2b078 mean?"
        - "Translate this Akamai error reference"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.post_json(
            "/edge-diagnostics/v1/error-translator",
            body={"errorCode": error_code},
        )

        logger.info("translate_error_code error_code=%s", error_code)

        translated = data.get("translatedError", {})
        return {
            "errorCode": error_code,
            "httpResponseCode": translated.get("httpResponseCode"),
            "timestamp": translated.get("timestamp"),
            "epochTime": translated.get("epochTime"),
            "clientIp": translated.get("clientIp"),
            "serverIp": translated.get("serverIp"),
            "originHostname": translated.get("originHostname"),
            "originIp": translated.get("originIp"),
            "userAgent": translated.get("userAgent"),
            "requestMethod": translated.get("requestMethod"),
            "reasonForFailure": translated.get("reasonForFailure"),
            "wafDetails": translated.get("wafDetails"),
            "logs": translated.get("logs", []),
        }
