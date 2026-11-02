"""EdgeWorker bundle cache — download, extract, and index code bundles in memory."""

from __future__ import annotations

import io
import logging
import re
import tarfile
from dataclasses import dataclass
from typing import Any

from cachetools import TTLCache

from mcp_akamai import validation as v
from mcp_akamai.client import AkamaiClient

logger = logging.getLogger(__name__)

# Largest bundle accepted, compressed download and extracted text alike.
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
# Total size of all cached bundles (approximate, extracted text counted twice:
# once as content and once split into lines).
MAX_CACHE_BYTES = 128 * 1024 * 1024
# Output caps for read_file and search_code.
MAX_READ_CHARS = 100_000
MAX_LINE_CHARS = 2_000
MAX_SEARCH_RESULTS = 200
MAX_MATCH_LINE_CHARS = 300


class BundleTooLargeError(ValueError):
    """The bundle exceeds MAX_BUNDLE_BYTES."""


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
    size_bytes: int = 0


class BundleCache:
    """TTL cache for EdgeWorker code bundles, capped by total size in bytes."""

    def __init__(self, max_bytes: int = MAX_CACHE_BYTES, ttl: int = 3600) -> None:
        self._cache: TTLCache[str, CachedBundle] = TTLCache(
            maxsize=max_bytes, ttl=ttl, getsizeof=lambda b: max(1, b.size_bytes)
        )

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

        version_path = v.edgeworker_version(version)
        raw = await client.get_bytes(f"/edgeworkers/v1/ids/{int(edgeworker_id)}/versions/{version_path}/content")
        if len(raw) > MAX_BUNDLE_BYTES:
            raise BundleTooLargeError(f"Bundle is {len(raw)} bytes, larger than the {MAX_BUNDLE_BYTES} byte limit")

        files: dict[str, CachedFile] = {}
        total = 0
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                if member.name.startswith("/") or ".." in member.name.split("/"):
                    continue
                total += member.size
                if total > MAX_BUNDLE_BYTES:
                    raise BundleTooLargeError(f"Extracted bundle exceeds the {MAX_BUNDLE_BYTES} byte limit")
                f = tar.extractfile(member)
                if f is None:
                    continue
                try:
                    content = f.read().decode("utf-8", errors="replace")
                except Exception:
                    continue
                lines = content.splitlines()
                files[member.name] = CachedFile(path=member.name, content=content, lines=lines)

        size = sum(2 * len(cf.content) for cf in files.values())
        bundle = CachedBundle(edgeworker_id=edgeworker_id, version=version, files=files, size_bytes=size)
        try:
            self._cache[self._key(edgeworker_id, version)] = bundle
        except ValueError:
            # Larger than the whole cache: serve it this once without caching.
            logger.warning("bundle_not_cached edgeworker_id=%d version=%s size=%d", edgeworker_id, version, size)
        logger.info("bundle_cached edgeworker_id=%d version=%s file_count=%d", edgeworker_id, version, len(files))
        return bundle

    def list_files(self, bundle: CachedBundle) -> list[dict[str, Any]]:
        """List files in a cached bundle with sizes and line counts."""
        return sorted(
            [{"path": cf.path, "lines": len(cf.lines), "size": len(cf.content)} for cf in bundle.files.values()],
            key=lambda x: x["path"],
        )

    def read_file(self, bundle: CachedBundle, path: str, start_line: int = 1, end_line: int | None = None) -> str:
        """Read a file from the cache by line range (1-based, inclusive).

        Lines longer than MAX_LINE_CHARS are shortened, and output stops at
        MAX_READ_CHARS with a note saying where to continue.
        """
        cf = bundle.files.get(path)
        if cf is None:
            return f"File not found: {path}"

        start_idx = max(0, start_line - 1)
        end_idx = end_line if end_line else len(cf.lines)
        selected = cf.lines[start_idx:end_idx]

        numbered: list[str] = []
        used = 0
        for i, line in enumerate(selected, start=start_idx + 1):
            if len(line) > MAX_LINE_CHARS:
                line = f"{line[:MAX_LINE_CHARS]} ... [line shortened, {len(line)} characters]"
            entry = f"{i:>4} | {line}"
            if numbered and used + len(entry) > MAX_READ_CHARS:
                numbered.append(f"[output truncated at {MAX_READ_CHARS} characters; continue with start_line={i}]")
                break
            numbered.append(entry)
            used += len(entry) + 1
        return "\n".join(numbered)

    def search_code(self, bundle: CachedBundle, pattern: str, max_results: int = 50) -> list[dict[str, Any]]:
        """Regex search across all files in a cached bundle."""
        max_results = max(1, min(MAX_SEARCH_RESULTS, max_results))
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
                    content = line.rstrip()
                    if len(content) > MAX_MATCH_LINE_CHARS:
                        content = content[:MAX_MATCH_LINE_CHARS] + " ..."
                    results.append({"file": cf.path, "line": i + 1, "content": content})
                    if len(results) >= max_results:
                        return results
        return results
