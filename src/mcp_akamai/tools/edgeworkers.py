"""EdgeWorker tools — list, browse code, and search across bundles."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_edgeworkers(
        ctx: Context,
    ) -> list[dict[str, Any]]:
        """List all EdgeWorkers with names and group associations.

        Example questions:
        - "What EdgeWorkers are configured?"
        - "Find the EdgeWorker for request routing"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get("/edgeworkers/v1/ids")
        items = data.get("edgeWorkerIds", [])

        results = []
        for ew in items:
            results.append(
                {
                    "edgeWorkerId": ew.get("edgeWorkerId"),
                    "name": ew.get("name"),
                    "groupId": ew.get("groupId"),
                    "description": ew.get("description", ""),
                }
            )

        logger.info("list_edgeworkers count=%d", len(results))
        return results

    @mcp.tool()
    async def list_edgeworker_versions(
        ctx: Context,
        edgeworker_id: Annotated[int, "EdgeWorker ID (numeric)"],
    ) -> list[dict[str, Any]]:
        """List versions for an EdgeWorker. Returns version identifiers,
        creation dates, and checksums.

        Example questions:
        - "What versions exist for EdgeWorker 42?"
        - "When was the latest version created?"
        """
        app = ctx.lifespan_context
        client = app.client

        data = await client.get(f"/edgeworkers/v1/ids/{edgeworker_id}/versions")
        items = data.get("versions", [])

        results = []
        for v in items:
            results.append(
                {
                    "edgeWorkerId": v.get("edgeWorkerId"),
                    "version": v.get("version"),
                    "createdBy": v.get("createdBy"),
                    "createdTime": v.get("createdTime"),
                    "checksum": v.get("checksum", ""),
                }
            )

        logger.info("list_edgeworker_versions edgeworker_id=%d count=%d", edgeworker_id, len(results))
        return results

    @mcp.tool()
    async def get_edgeworker_files(
        ctx: Context,
        edgeworker_id: Annotated[int, "EdgeWorker ID (numeric)"],
        version: Annotated[str, "Version identifier (e.g., '1.0')"],
    ) -> list[dict[str, Any]]:
        """List files in an EdgeWorker version's code bundle. Returns
        file paths, sizes, and line counts.

        Example questions:
        - "What files are in EdgeWorker 42 version 1.0?"
        - "Show me the file listing for this EdgeWorker"
        """
        app = ctx.lifespan_context
        bundle = await app.bundle_cache.load(app.client, edgeworker_id, version)
        files = app.bundle_cache.list_files(bundle)
        logger.info("get_edgeworker_files edgeworker_id=%d version=%s files=%d", edgeworker_id, version, len(files))
        return files

    @mcp.tool()
    async def get_edgeworker_file(
        ctx: Context,
        edgeworker_id: Annotated[int, "EdgeWorker ID (numeric)"],
        version: Annotated[str, "Version identifier (e.g., '1.0')"],
        path: Annotated[str, "File path within the bundle (e.g., 'main.js')"],
        start_line: Annotated[int, "First line to read (1-based, inclusive)"] = 1,
        end_line: Annotated[int | None, "Last line to read (1-based, inclusive). Omit to read to end."] = None,
    ) -> str:
        """Read a file from an EdgeWorker code bundle. Returns numbered
        source lines.

        Example questions:
        - "Show me main.js from EdgeWorker 42 v1.0"
        - "Read lines 50-100 of the request handler"
        """
        app = ctx.lifespan_context
        bundle = await app.bundle_cache.load(app.client, edgeworker_id, version)
        content = app.bundle_cache.read_file(bundle, path, start_line, end_line)
        logger.info("get_edgeworker_file edgeworker_id=%d version=%s path=%s", edgeworker_id, version, path)
        return content

    @mcp.tool()
    async def search_edgeworker_code(
        ctx: Context,
        edgeworker_id: Annotated[int, "EdgeWorker ID (numeric)"],
        version: Annotated[str, "Version identifier (e.g., '1.0')"],
        pattern: Annotated[str, "Regex pattern to search for (case-insensitive)"],
        max_results: Annotated[int, "Maximum number of matches to return"] = 50,
    ) -> list[dict[str, Any]]:
        """Search across all files in an EdgeWorker code bundle using a regex
        pattern. Returns matching file paths, line numbers, and content.

        Example questions:
        - "Find all uses of 'setResponseHeader' in this EdgeWorker"
        - "Search for error handling patterns"
        """
        app = ctx.lifespan_context
        bundle = await app.bundle_cache.load(app.client, edgeworker_id, version)
        results = app.bundle_cache.search_code(bundle, pattern, max_results)
        logger.info(
            "search_edgeworker_code edgeworker_id=%d version=%s pattern=%s matches=%d",
            edgeworker_id,
            version,
            pattern,
            len(results),
        )
        return results
