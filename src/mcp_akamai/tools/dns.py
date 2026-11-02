"""Edge DNS tools — list zones and search DNS records."""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP

from mcp_akamai import validation as v

logger = logging.getLogger(__name__)

# Most records returned by search_dns_records; narrow with search or record_type.
MAX_DNS_RECORDS = 500


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_dns_zones(
        ctx: Context,
        search: Annotated[str | None, "Filter zone names by substring"] = None,
        zone_type: Annotated[Literal["PRIMARY", "SECONDARY", "ALIAS"] | None, "Filter by zone type"] = None,
    ) -> list[dict[str, Any]]:
        """List DNS zones. Returns zone names, types, and activation state.

        Example questions:
        - "What DNS zones are managed in Akamai?"
        - "Find the DNS zone for example.com"
        """
        app = ctx.lifespan_context
        client = app.client

        params: dict[str, Any] = {"showAll": "true"}
        if search:
            params["search"] = search
        if zone_type:
            params["types"] = zone_type

        data = await client.get("/config-dns/v2/zones", params=params)
        zones = data.get("zones", [])

        results = []
        for z in zones:
            results.append(
                {
                    "zone": z.get("zone"),
                    "type": z.get("type"),
                    "comment": z.get("comment", ""),
                    "activationState": z.get("activationState"),
                }
            )

        logger.info("list_dns_zones count=%d", len(results))
        return results

    @mcp.tool()
    async def search_dns_records(
        ctx: Context,
        zone: Annotated[str, "DNS zone name (e.g., example.com)"],
        search: Annotated[str | None, "Filter by record name"] = None,
        record_type: Annotated[str | None, "Filter by record type: A, AAAA, CNAME, MX, TXT, etc."] = None,
    ) -> dict[str, Any]:
        """Get DNS records for a zone. Returns record names, types, TTLs,
        and values, at most 500 records; "truncated" is set when the zone has
        more, so narrow the search with a name or record type.

        Example questions:
        - "What DNS records exist for example.com?"
        - "Find all CNAME records in the example.com zone"
        """
        zone_path = v.zone(zone)
        app = ctx.lifespan_context
        client = app.client

        params: dict[str, Any] = {"showAll": "true"}
        if search:
            params["search"] = search
        if record_type:
            params["types"] = record_type

        data = await client.get(f"/config-dns/v2/zones/{zone_path}/recordsets", params=params)
        recordsets = data.get("recordsets", [])

        results = []
        for rs in recordsets[:MAX_DNS_RECORDS]:
            results.append(
                {
                    "name": rs.get("name"),
                    "type": rs.get("type"),
                    "ttl": rs.get("ttl"),
                    "rdata": rs.get("rdata", []),
                }
            )

        logger.info("search_dns_records zone=%s count=%d total=%d", zone, len(results), len(recordsets))
        response: dict[str, Any] = {"zone": zone, "records": results, "count": len(results)}
        if len(recordsets) > MAX_DNS_RECORDS:
            response["truncated"] = True
            response["totalRecords"] = len(recordsets)
            response["note"] = f"Only the first {MAX_DNS_RECORDS} records are shown; filter by name or record type."
        return response
