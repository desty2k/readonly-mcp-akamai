"""Network list tools — search and inspect IP/geo allow/block lists."""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP

from mcp_akamai import validation as v

logger = logging.getLogger(__name__)

# Most entries returned by get_network_list.
MAX_LIST_ELEMENTS = 5000


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

        logger.info("search_network_lists count=%d", len(results))
        return results

    @mcp.tool()
    async def get_network_list(
        ctx: Context,
        unique_id: Annotated[str, "Network list unique ID (e.g., 12345_BLOCKLIST)"],
    ) -> dict[str, Any]:
        """Get the contents of a network list. Returns metadata and the IP,
        CIDR, or country code entries, at most 5000; "truncated" is set when
        the list has more.

        Example questions:
        - "What IPs are in the blocklist?"
        - "Show all entries in network list 12345_ALLOWLIST"
        - "Which countries are in the geo restriction list?"
        """
        list_path = v.network_list_id(unique_id)
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(
            f"/network-list/v2/network-lists/{list_path}",
            params={"includeElements": "true"},
        )

        logger.info("get_network_list unique_id=%s elements=%s", unique_id, data.get("elementCount"))

        elements = data.get("list", [])
        response: dict[str, Any] = {
            "uniqueId": data.get("uniqueId"),
            "name": data.get("name"),
            "type": data.get("type"),
            "elementCount": data.get("elementCount"),
            "description": data.get("description", ""),
            "list": elements[:MAX_LIST_ELEMENTS],
        }
        if len(elements) > MAX_LIST_ELEMENTS:
            response["truncated"] = True
            response["note"] = f"Only the first {MAX_LIST_ELEMENTS} of {len(elements)} entries are shown."
        return response
