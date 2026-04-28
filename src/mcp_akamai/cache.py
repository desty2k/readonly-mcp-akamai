"""EdgeWorker bundle cache — download, extract, and index code bundles in memory."""

from __future__ import annotations

import io
import logging
import re
import tarfile
from dataclasses import dataclass
from typing import Any

from cachetools import TTLCache

from mcp_akamai.client import AkamaiClient

logger = logging.getLogger(__name__)


@dataclass
class CachedFile:
    """A single file extracted from an EdgeWorker bundle."""

    path: str
    content: str
    lines: list[str]


@dataclass
class CachedBundle:
    """An extracted EdgeWorker code bundle held in memory."""

    edgeworker_id: int
    version: str
    files: dict[str, CachedFile]


class BundleCache:
    """TTL cache for EdgeWorker code bundles. Uses cachetools.TTLCache."""

    def __init__(self, maxsize: int = 50, ttl: int = 3600) -> None:
        self._cache: TTLCache[str, CachedBundle] = TTLCache(maxsize=maxsize, ttl=ttl)

    def _key(self, edgeworker_id: int, version: str) -> str:
        return f"{edgeworker_id}:{version}"

    def get(self, edgeworker_id: int, version: str) -> CachedBundle | None:
        """Get a cached bundle if it exists and is not expired."""
        return self._cache.get(self._key(edgeworker_id, version))

    async def load(self, client: AkamaiClient, edgeworker_id: int, version: str) -> CachedBundle:
        """Download, extract, and cache an EdgeWorker bundle."""
        cached = self.get(edgeworker_id, version)
        if cached:
            return cached

        logger.info("bundle_download_started edgeworker_id=%d version=%s", edgeworker_id, version)

        raw = await client.get_bytes(f"/edgeworkers/v1/ids/{edgeworker_id}/versions/{version}/content")

        files: dict[str, CachedFile] = {}
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                if member.name.startswith("/") or ".." in member.name.split("/"):
                    continue
                f = tar.extractfile(member)
                if f is None:
                    continue
                try:
                    content = f.read().decode("utf-8", errors="replace")
                except Exception:
                    continue
                lines = content.splitlines()
                files[member.name] = CachedFile(path=member.name, content=content, lines=lines)

        bundle = CachedBundle(edgeworker_id=edgeworker_id, version=version, files=files)
        self._cache[self._key(edgeworker_id, version)] = bundle
        logger.info("bundle_cached edgeworker_id=%d version=%s file_count=%d", edgeworker_id, version, len(files))
        return bundle

    def list_files(self, bundle: CachedBundle) -> list[dict[str, Any]]:
        """List files in a cached bundle with sizes and line counts."""
        return sorted(
            [{"path": cf.path, "lines": len(cf.lines), "size": len(cf.content)} for cf in bundle.files.values()],
            key=lambda x: x["path"],
        )

    def read_file(self, bundle: CachedBundle, path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """Read a file from the cache by line range (1-based, inclusive)."""
        cf = bundle.files.get(path)
        if cf is None:
            return f"File not found: {path}"

        start_idx = max(0, start_line - 1)
        end_idx = end_line if end_line else len(cf.lines)
        selected = cf.lines[start_idx:end_idx]

        numbered = []
        for i, line in enumerate(selected, start=start_idx + 1):
            numbered.append(f"{i:>4} | {line}")
        return "\n".join(numbered)

    def search_code(self, bundle: CachedBundle, pattern: str, max_results: int = 50) -> list[dict[str, Any]]:
        """Regex search across all files in a cached bundle."""
        if len(pattern) > 500:
            return [{"error": "Pattern too long (max 500 characters)"}]
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return [{"error": f"Invalid regex: {e}"}]

        results: list[dict[str, Any]] = []
        for cf in bundle.files.values():
            for i, line in enumerate(cf.lines):
                if compiled.search(line):
                    results.append({"file": cf.path, "line": i + 1, "content": line.rstrip()})
                    if len(results) >= max_results:
                        return results
        return results
