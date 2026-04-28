"""Property Manager tools — search, inspect, and review CDN configurations."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def search_properties(
        ctx: Context,
        query: Annotated[str, "Property name or partial name to search for"],
        limit: Annotated[int, "Maximum number of results to return (1-50)"] = 10,
    ) -> list[dict[str, Any]]:
        """Search CDN properties by name. Returns matching properties with
        version numbers, staging/production versions, and group/contract IDs.

        Example questions:
        - "Find the CDN config for example.com"
        - "Which property handles api.example.com?"
        """
        app = ctx.lifespan_context
        limit = max(1, min(50, limit))
        results = app.property_index.search(query, limit=limit)
        logger.info("search_properties query=%s results=%d", query, len(results))
        return results

    @mcp.tool()
    async def get_property_details(
        ctx: Context,
        property_id: Annotated[str, "Akamai property ID (e.g., prp_12345)"],
        contract_id: Annotated[str, "Contract ID (e.g., ctr_1-AB123)"],
        group_id: Annotated[str, "Group ID (e.g., grp_12345)"],
    ) -> dict[str, Any]:
        """Get property versions, hostnames, and activation status for staging
        and production networks.

        Example questions:
        - "What version is deployed to production for this property?"
        - "What hostnames does this property serve?"
        """
        app = ctx.lifespan_context
        client = app.client
        # Get property metadata
        prop_data = await client.get(
            f"/papi/v1/properties/{property_id}",
            params={"contractId": contract_id, "groupId": group_id},
        )
        items = prop_data.get("properties", {}).get("items", [])
        if not items:
            return {"error": f"Property {property_id} not found in contract {contract_id} / group {group_id}"}
        prop = items[0]

        # Get hostnames for the latest version
        latest_version = prop.get("latestVersion", 1)
        hostnames_data = await client.get(
            f"/papi/v1/properties/{property_id}/versions/{latest_version}/hostnames",
            params={"contractId": contract_id, "groupId": group_id},
        )
        hostnames = [
            {
                "cnameFrom": h.get("cnameFrom"),
                "cnameTo": h.get("cnameTo"),
                "cnameType": h.get("cnameType"),
            }
            for h in hostnames_data.get("hostnames", {}).get("items", [])
        ]

        logger.info("get_property_details property_id=%s latest_version=%d", property_id, latest_version)

        return {
            "propertyId": prop.get("propertyId"),
            "propertyName": prop.get("propertyName"),
            "contractId": prop.get("contractId"),
            "groupId": prop.get("groupId"),
            "latestVersion": prop.get("latestVersion"),
            "stagingVersion": prop.get("stagingVersion"),
            "productionVersion": prop.get("productionVersion"),
            "note": prop.get("note", ""),
            "hostnames": hostnames,
        }

    @mcp.tool()
    async def get_property_rules(
        ctx: Context,
        property_id: Annotated[str, "Akamai property ID (e.g., prp_12345)"],
        version: Annotated[int, "Property version number"],
        contract_id: Annotated[str, "Contract ID (e.g., ctr_1-AB123)"],
        group_id: Annotated[str, "Group ID (e.g., grp_12345)"],
    ) -> dict[str, Any]:
        """Get the rule tree for a property version. Returns the CDN
        configuration as nested rules with match criteria and behaviors:
        caching, origin settings, headers, redirects, and edge logic.

        Example questions:
        - "What caching rules are set for this property?"
        - "Show me the origin configuration"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(
            f"/papi/v1/properties/{property_id}/versions/{version}/rules",
            params={"contractId": contract_id, "groupId": group_id},
        )

        rules = data.get("rules", {})
        logger.info("get_property_rules property_id=%s version=%d", property_id, version)

        return {
            "propertyId": property_id,
            "version": version,
            "ruleFormat": data.get("ruleFormat"),
            "rules": _slim_rules(rules),
        }

    @mcp.tool()
    async def get_property_activations(
        ctx: Context,
        property_id: Annotated[str, "Akamai property ID (e.g., prp_12345)"],
        contract_id: Annotated[str, "Contract ID (e.g., ctr_1-AB123)"],
        group_id: Annotated[str, "Group ID (e.g., grp_12345)"],
    ) -> list[dict[str, Any]]:
        """Get activation history for a property. Returns which versions
        were deployed to staging and production, when, and by whom.

        Example questions:
        - "When was the last production deployment for this property?"
        - "Who activated version 12?"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(
            f"/papi/v1/properties/{property_id}/activations",
            params={"contractId": contract_id, "groupId": group_id},
        )

        activations = []
        for act in data.get("activations", {}).get("items", []):
            activations.append(
                {
                    "activationId": act.get("activationId"),
                    "propertyVersion": act.get("propertyVersion"),
                    "network": act.get("network"),
                    "activationType": act.get("activationType"),
                    "status": act.get("status"),
                    "submitDate": act.get("submitDate"),
                    "updateDate": act.get("updateDate"),
                    "note": act.get("note", ""),
                    "notifyEmails": act.get("notifyEmails", []),
                }
            )

        logger.info("get_property_activations property_id=%s count=%d", property_id, len(activations))
        return activations


def _slim_rules(rules: dict[str, Any]) -> dict[str, Any]:
    """Recursively strip verbose metadata from the rule tree, keeping structure."""
    result: dict[str, Any] = {"name": rules.get("name", "")}

    criteria = rules.get("criteria")
    if criteria:
        result["criteria"] = [{"name": c.get("name"), "options": c.get("options", {})} for c in criteria]

    behaviors = rules.get("behaviors")
    if behaviors:
        result["behaviors"] = [{"name": b.get("name"), "options": b.get("options", {})} for b in behaviors]

    children = rules.get("children")
    if children:
        result["children"] = [_slim_rules(child) for child in children]

    comments = rules.get("comments")
    if comments:
        result["comments"] = comments

    return result
