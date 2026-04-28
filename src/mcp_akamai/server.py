"""FastMCP server with lifespan, instructions, and tool registration."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastmcp import FastMCP

from mcp_akamai.cache import BundleCache
from mcp_akamai.client import AkamaiClient
from mcp_akamai.index import PropertyIndex
from mcp_akamai.settings import AkamaiSettings

logger = logging.getLogger(__name__)

MCP_INSTRUCTIONS = """\
Read-only access to Akamai CDN configuration. This server can search and inspect \
properties, DNS zones, EdgeWorker code, network lists, and CP codes. It cannot \
create, modify, delete, activate, deactivate, or purge anything.

## Key Akamai Concepts

**Property** — An Akamai CDN configuration that defines how traffic is handled \
for one or more hostnames. Properties contain a rule tree (nested match conditions \
and behaviors) that controls caching, routing, headers, and edge logic.

**Group** — An organizational container in the Akamai account. Properties belong \
to groups. Groups are arranged hierarchically.

**Contract** — A billing/entitlement container. Properties are scoped to a \
contract. Most API calls require a contractId.

**CP Code (Content Provider Code)** — A numeric identifier used for billing \
and reporting. Every property references one or more CP codes in its rules.

**EdgeWorker** — A serverless JavaScript function that runs on Akamai edge \
servers. EdgeWorkers intercept and transform requests/responses at the CDN layer.

**Network List** — A named collection of IP addresses, CIDR blocks, or \
geographic identifiers. Used in property rules for access control and routing.

## Workflow: Investigating a CDN Configuration

1. Search for the property by name using fuzzy search
2. Get property details to see versions, hostnames, and activation status
3. Get the rule tree to inspect the full CDN configuration
4. Check activations to see deployment history

## Workflow: Browsing EdgeWorker Code

1. List EdgeWorkers to find the right one by name
2. List versions for that EdgeWorker
3. Download and list files in a version's code bundle
4. Read specific files by path and line range
5. Search across all files in the bundle with regex

## Notes

- Property search is fuzzy by name. The index is preloaded at startup and \
refreshed periodically. Results include a match score.
- Empty results mean no matches were found, not an error.
- Property rules are deeply nested JSON. The top-level "default" rule contains \
children, each with match criteria and behaviors.
- DNS record search is within a specific zone. You need the zone name first.
- Network lists can contain IPs, CIDRs, or country codes depending on type.
"""


@dataclass
class AppContext:
    """Shared application state available to all tools."""

    client: AkamaiClient
    settings: AkamaiSettings
    property_index: PropertyIndex
    bundle_cache: BundleCache


def create_server(settings: AkamaiSettings | None = None) -> FastMCP:
    """Build and return the configured FastMCP server."""
    if settings is None:
        settings = AkamaiSettings()  # type: ignore[call-arg]

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
        logger.info("server_starting transport=%s", settings.transport)

        api_client = AkamaiClient(settings)
        prop_index = PropertyIndex()
        bundle_cache = BundleCache()

        # Preload the property index
        await prop_index.load(api_client)
        await prop_index.start_background_refresh(api_client, settings.index_refresh_interval)

        logger.info("server_ready properties_indexed=%d", prop_index.size)

        try:
            yield AppContext(
                client=api_client,
                settings=settings,
                property_index=prop_index,
                bundle_cache=bundle_cache,
            )
        finally:
            await prop_index.stop()
            await api_client.close()
            logger.info("server_stopped")

    mcp = FastMCP(
        "Akamai CDN",
        instructions=MCP_INSTRUCTIONS,
        lifespan=lifespan,
    )

    # Register all tool modules
    from mcp_akamai.tools import dns, edgeworkers, network_lists, properties, utility

    for module in [properties, dns, edgeworkers, network_lists, utility]:
        module.register(mcp)

    return mcp
