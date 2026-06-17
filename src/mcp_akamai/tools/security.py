"""Application Security tools — inspect WAF policies, IP/GEO firewall rules."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_security_configs(
        ctx: Context,
    ) -> list[dict[str, Any]]:
        """List all Application Security configurations.

        Example questions:
        - "What WAF configurations exist?"
        - "Which security configs are active?"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get("/appsec/v1/configs")
        configs = data.get("configurations", [])

        results = []
        for cfg in configs:
            results.append(
                {
                    "configId": cfg.get("id"),
                    "name": cfg.get("name"),
                    "description": cfg.get("description", ""),
                    "latestVersion": cfg.get("latestVersion"),
                    "stagingVersion": cfg.get("stagingVersion"),
                    "productionVersion": cfg.get("productionVersion"),
                }
            )

        logger.info("list_security_configs count=%d", len(results))
        return results

    @mcp.tool()
    async def get_security_policy_list(
        ctx: Context,
        config_id: Annotated[int, "Security configuration ID"],
        version: Annotated[int, "Configuration version number"],
    ) -> list[dict[str, Any]]:
        """List security policies within a configuration version.

        Example questions:
        - "What security policies are in this WAF config?"
        - "Show me the policies for config 12345"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(
            f"/appsec/v1/configs/{config_id}/versions/{version}/security-policies"
        )
        policies = data.get("policies", [])

        results = []
        for pol in policies:
            results.append(
                {
                    "policyId": pol.get("policyId"),
                    "policyName": pol.get("policyName"),
                    "hasRatePolicyWithApiKey": pol.get("hasRatePolicyWithApiKey"),
                    "policySecurityControls": pol.get("policySecurityControls"),
                }
            )

        logger.info("get_security_policy_list config=%d version=%d count=%d", config_id, version, len(results))
        return results

    @mcp.tool()
    async def get_ip_geo_firewall(
        ctx: Context,
        config_id: Annotated[int, "Security configuration ID"],
        version: Annotated[int, "Configuration version number"],
        policy_id: Annotated[str, "Security policy ID (e.g., 'pol1')"],
    ) -> dict[str, Any]:
        """Get IP/GEO firewall settings for a security policy. Shows which
        network lists are used as allow/block lists for IP and GEO controls.

        Example questions:
        - "What IPs are blocked by this WAF policy?"
        - "Which network lists are used for geo blocking?"
        - "Is ifood-partners allowlisted in this policy?"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(
            f"/appsec/v1/configs/{config_id}/versions/{version}/security-policies/{policy_id}/ip-geo-firewall"
        )

        logger.info("get_ip_geo_firewall config=%d version=%d policy=%s", config_id, version, policy_id)
        return data

    @mcp.tool()
    async def get_security_config_hostnames(
        ctx: Context,
        config_id: Annotated[int, "Security configuration ID"],
        version: Annotated[int, "Configuration version number"],
    ) -> list[str]:
        """List hostnames protected by a security configuration version.

        Example questions:
        - "Which hostnames are covered by this WAF config?"
        - "Is acessos.ifoodcorp.com.br protected by a WAF?"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(
            f"/appsec/v1/configs/{config_id}/versions/{version}/selected-hostnames"
        )
        hostnames = data.get("hostnameList", [])

        result = [h.get("hostname", "") for h in hostnames]

        logger.info("get_security_config_hostnames config=%d version=%d count=%d", config_id, version, len(result))
        return result
