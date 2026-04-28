"""Network list tools — search and inspect IP/geo allow/block lists."""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def search_network_lists(
        ctx: Context,
        search: Annotated[str | None, "Filter by network list name"] = None,
        list_type: Annotated[Literal["IP", "GEO"] | None, "Filter by type"] = None,
    ) -> list[dict[str, Any]]:
        """Search network lists by name. Network lists are collections of
        IP addresses, CIDR blocks, or country codes used for access control.

        Example questions:
        - "What network lists are configured?"
        - "Find the blocklist for bad IPs"
        - "Are there any geo-restriction lists?"
        """
        app = ctx.lifespan_context
        client = app.client

        params: dict[str, Any] = {"includeElements": "false"}
        if search:
            params["search"] = search
        if list_type:
            params["listType"] = list_type

        data = await client.get("/network-list/v2/network-lists", params=params)
        lists = data.get("networkLists", [])

        results = []
        for nl in lists:
            results.append(
                {
                    "uniqueId": nl.get("uniqueId"),
                    "name": nl.get("name"),
                    "type": nl.get("type"),
                    "elementCount": nl.get("elementCount"),
                    "syncPoint": nl.get("syncPoint"),
                    "description": nl.get("description", ""),
                }
            )

        logger.info("search_network_lists count=%d search=%s", len(results), search)
        return results

    @mcp.tool()
    async def get_network_list(
        ctx: Context,
        unique_id: Annotated[str, "Network list unique ID (e.g., 12345_BLOCKLIST)"],
    ) -> dict[str, Any]:
        """Get the full contents of a network list. Returns metadata and
        every IP, CIDR, or country code entry.

        Example questions:
        - "What IPs are in the blocklist?"
        - "Show all entries in network list 12345_ALLOWLIST"
        - "Which countries are in the geo restriction list?"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(
            f"/network-list/v2/network-lists/{unique_id}",
            params={"includeElements": "true"},
        )

        logger.info("get_network_list unique_id=%s elements=%s", unique_id, data.get("elementCount"))

        return {
            "uniqueId": data.get("uniqueId"),
            "name": data.get("name"),
            "type": data.get("type"),
            "elementCount": data.get("elementCount"),
            "description": data.get("description", ""),
            "list": data.get("list", []),
        }
