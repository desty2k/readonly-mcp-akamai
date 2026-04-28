"""Tests for EdgeWorker tools."""

from __future__ import annotations

import io
import tarfile
from unittest.mock import AsyncMock, MagicMock

from helpers import extract_tools


def _make_tgz(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class TestListEdgeworkers:
    async def test_returns_edgeworkers(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "edgeWorkerIds": [
                    {
                        "edgeWorkerId": 42,
                        "name": "Request Router",
                        "groupId": "grp_1",
                        "description": "Routes requests to origins",
                        "internalField": "stripped",
                    },
                    {
                        "edgeWorkerId": 43,
                        "name": "Header Modifier",
                        "groupId": "grp_1",
                        "description": "",
                    },
                ]
            }
        )

        from mcp_akamai.tools import edgeworkers

        tools = extract_tools(edgeworkers)
        results = await tools["list_edgeworkers"](mock_ctx)

        assert len(results) == 2
        assert results[0]["edgeWorkerId"] == 42
        assert results[0]["name"] == "Request Router"
        assert "internalField" not in results[0]


class TestListEdgeworkerVersions:
    async def test_returns_versions(self, mock_ctx: MagicMock) -> None:
        client = mock_ctx.lifespan_context.client
        client.get = AsyncMock(
            return_value={
                "versions": [
                    {
                        "edgeWorkerId": 42,
                        "version": "1.0",
                        "createdBy": "user@example.com",
                        "createdTime": "2025-01-01T00:00:00Z",
                        "checksum": "abc123",
                    },
                ]
            }
        )

        from mcp_akamai.tools import edgeworkers

        tools = extract_tools(edgeworkers)
        results = await tools["list_edgeworker_versions"](mock_ctx, edgeworker_id=42)

        assert len(results) == 1
        assert results[0]["version"] == "1.0"
        assert results[0]["createdBy"] == "user@example.com"


class TestGetEdgeworkerFiles:
    async def test_downloads_and_lists_files(self, mock_ctx: MagicMock) -> None:
        tgz = _make_tgz({"main.js": "console.log('hi');", "bundle.json": '{"v":"1"}'})
        mock_ctx.lifespan_context.client.get_bytes = AsyncMock(return_value=tgz)

        from mcp_akamai.tools import edgeworkers

        tools = extract_tools(edgeworkers)
        results = await tools["get_edgeworker_files"](mock_ctx, edgeworker_id=42, version="1.0")

        assert len(results) == 2
        paths = [f["path"] for f in results]
        assert "main.js" in paths
        assert "bundle.json" in paths

    async def test_cache_reuse(self, mock_ctx: MagicMock) -> None:
        tgz = _make_tgz({"a.js": "x"})
        mock_ctx.lifespan_context.client.get_bytes = AsyncMock(return_value=tgz)

        from mcp_akamai.tools import edgeworkers

        tools = extract_tools(edgeworkers)
        await tools["get_edgeworker_files"](mock_ctx, edgeworker_id=42, version="1.0")
        await tools["get_edgeworker_files"](mock_ctx, edgeworker_id=42, version="1.0")

        # Should only download once
        mock_ctx.lifespan_context.client.get_bytes.assert_called_once()


class TestGetEdgeworkerFile:
    async def test_reads_file(self, mock_ctx: MagicMock) -> None:
        tgz = _make_tgz({"main.js": "line1\nline2\nline3"})
        mock_ctx.lifespan_context.client.get_bytes = AsyncMock(return_value=tgz)

        from mcp_akamai.tools import edgeworkers

        tools = extract_tools(edgeworkers)
        # First load the bundle
        await tools["get_edgeworker_files"](mock_ctx, edgeworker_id=42, version="1.0")

        content = await tools["get_edgeworker_file"](mock_ctx, edgeworker_id=42, version="1.0", path="main.js")
        assert "line1" in content
        assert "line2" in content
        assert "line3" in content

    async def test_reads_line_range(self, mock_ctx: MagicMock) -> None:
        tgz = _make_tgz({"main.js": "line1\nline2\nline3\nline4\nline5"})
        mock_ctx.lifespan_context.client.get_bytes = AsyncMock(return_value=tgz)

        from mcp_akamai.tools import edgeworkers

        tools = extract_tools(edgeworkers)
        await tools["get_edgeworker_files"](mock_ctx, edgeworker_id=42, version="1.0")

        content = await tools["get_edgeworker_file"](
            mock_ctx, edgeworker_id=42, version="1.0", path="main.js", start_line=2, end_line=3
        )
        assert "line2" in content
        assert "line3" in content
        assert "line1" not in content
        assert "line4" not in content


class TestSearchEdgeworkerCode:
    async def test_searches_across_files(self, mock_ctx: MagicMock) -> None:
        tgz = _make_tgz(
            {
                "main.js": "import { handler } from './util';\nhandler();",
                "util.js": "export function handler() { return true; }",
            }
        )
        mock_ctx.lifespan_context.client.get_bytes = AsyncMock(return_value=tgz)

        from mcp_akamai.tools import edgeworkers

        tools = extract_tools(edgeworkers)
        await tools["get_edgeworker_files"](mock_ctx, edgeworker_id=42, version="1.0")

        results = await tools["search_edgeworker_code"](mock_ctx, edgeworker_id=42, version="1.0", pattern="handler")
        assert len(results) >= 2
        files = {r["file"] for r in results}
        assert "main.js" in files
        assert "util.js" in files

    async def test_search_no_match(self, mock_ctx: MagicMock) -> None:
        tgz = _make_tgz({"main.js": "console.log('hi');"})
        mock_ctx.lifespan_context.client.get_bytes = AsyncMock(return_value=tgz)

        from mcp_akamai.tools import edgeworkers

        tools = extract_tools(edgeworkers)
        await tools["get_edgeworker_files"](mock_ctx, edgeworker_id=42, version="1.0")

        results = await tools["search_edgeworker_code"](
            mock_ctx, edgeworker_id=42, version="1.0", pattern="zzzznothere"
        )
        assert results == []
