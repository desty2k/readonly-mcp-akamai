"""Tests for the EdgeWorker bundle cache."""

from __future__ import annotations

import io
import tarfile
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_akamai import cache as cache_mod
from mcp_akamai.cache import BundleCache, CachedBundle, CachedFile


def _make_tgz(files: dict[str, str]) -> bytes:
    """Create an in-memory tgz archive from a dict of {path: content}."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@pytest.fixture
def sample_bundle() -> CachedBundle:
    """A pre-built cached bundle for testing reads and searches."""
    return CachedBundle(
        edgeworker_id=42,
        version="1.0",
        files={
            "main.js": CachedFile(
                path="main.js",
                content=(
                    "import { logger } from './utils';\n\nexport function onClientRequest(request)"
                    " {\n  logger.log('handling request');\n  return request;\n}\n"
                ),
                lines=[
                    "import { logger } from './utils';",
                    "",
                    "export function onClientRequest(request) {",
                    "  logger.log('handling request');",
                    "  return request;",
                    "}",
                ],
            ),
            "utils.js": CachedFile(
                path="utils.js",
                content="export const logger = { log: (msg) => console.log(msg) };\n",
                lines=["export const logger = { log: (msg) => console.log(msg) };"],
            ),
            "bundle.json": CachedFile(
                path="bundle.json",
                content='{"edgeworker-version": "1.0"}',
                lines=['{"edgeworker-version": "1.0"}'],
            ),
        },
    )


class TestBundleCacheLoad:
    async def test_download_and_extract(self) -> None:
        tgz = _make_tgz({"main.js": "console.log('hello');", "bundle.json": '{"v": 1}'})

        client = MagicMock()
        client.get_bytes = AsyncMock(return_value=tgz)

        cache = BundleCache()
        bundle = await cache.load(client, 42, "1.0")

        assert bundle.edgeworker_id == 42
        assert bundle.version == "1.0"
        assert "main.js" in bundle.files
        assert "bundle.json" in bundle.files
        assert bundle.files["main.js"].lines == ["console.log('hello');"]

    async def test_cache_hit(self) -> None:
        tgz = _make_tgz({"a.js": "x"})

        client = MagicMock()
        client.get_bytes = AsyncMock(return_value=tgz)

        cache = BundleCache()
        b1 = await cache.load(client, 1, "1.0")
        b2 = await cache.load(client, 1, "1.0")

        assert b1 is b2
        client.get_bytes.assert_called_once()

    async def test_different_versions_cached_separately(self) -> None:
        client = MagicMock()
        client.get_bytes = AsyncMock(side_effect=[_make_tgz({"a.js": "v1"}), _make_tgz({"a.js": "v2"})])

        cache = BundleCache()
        b1 = await cache.load(client, 1, "1.0")
        b2 = await cache.load(client, 1, "2.0")

        assert b1 is not b2
        assert b1.files["a.js"].content == "v1"
        assert b2.files["a.js"].content == "v2"


class TestBundleCacheListFiles:
    def test_list_files(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        files = cache.list_files(sample_bundle)

        assert len(files) == 3
        paths = [f["path"] for f in files]
        assert "main.js" in paths
        assert "utils.js" in paths
        assert "bundle.json" in paths

        main = next(f for f in files if f["path"] == "main.js")
        assert main["lines"] == 6
        assert main["size"] > 0


class TestBundleCacheReadFile:
    def test_read_full_file(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        content = cache.read_file(sample_bundle, "main.js")

        assert "1 |" in content
        assert "onClientRequest" in content

    def test_read_line_range(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        content = cache.read_file(sample_bundle, "main.js", start_line=3, end_line=4)

        lines = content.strip().split("\n")
        assert len(lines) == 2
        assert "onClientRequest" in lines[0]

    def test_read_nonexistent_file(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        content = cache.read_file(sample_bundle, "nonexistent.js")
        assert "File not found" in content


class TestBundleCacheSearch:
    def test_search_finds_matches(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        results = cache.search_code(sample_bundle, "logger")

        assert len(results) >= 2
        files_matched = {r["file"] for r in results}
        assert "main.js" in files_matched
        assert "utils.js" in files_matched

    def test_search_respects_max_results(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        results = cache.search_code(sample_bundle, ".", max_results=2)
        assert len(results) == 2

    def test_search_no_match(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        results = cache.search_code(sample_bundle, "zzzznothere")
        assert results == []

    def test_search_invalid_regex(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        results = cache.search_code(sample_bundle, "[invalid")
        assert len(results) == 1
        assert "error" in results[0]

    def test_search_result_shape(self, sample_bundle: CachedBundle) -> None:
        cache = BundleCache()
        results = cache.search_code(sample_bundle, "onClientRequest")
        assert len(results) >= 1
        r = results[0]
        assert "file" in r
        assert "line" in r
        assert "content" in r


class TestBundleCacheEviction:
    def test_expired_entries_evicted(self) -> None:
        cache = BundleCache(ttl=1)  # 1 second TTL
        bundle = CachedBundle(
            edgeworker_id=1,
            version="1.0",
            files={},
        )
        cache._cache[cache._key(1, "1.0")] = bundle

        # Should be present immediately
        assert cache.get(1, "1.0") is not None

        # Wait for TTL to expire
        time.sleep(1.1)
        result = cache.get(1, "1.0")
        assert result is None


class TestCaps:
    def test_read_file_stops_at_char_cap(self) -> None:
        line = "x" * 1000
        bundle = CachedBundle(1, "1.0", {"big.js": CachedFile("big.js", "", [line] * 500)})
        out = BundleCache().read_file(bundle, "big.js")
        assert len(out) < cache_mod.MAX_READ_CHARS + 200
        last = out.splitlines()[-1]
        assert last.startswith("[output truncated")
        next_line = int(last.split("start_line=")[1].rstrip("]"))
        assert f"{next_line - 1:>4} | " in out
        assert f"{next_line:>4} | " not in out

    def test_read_file_shortens_long_lines(self) -> None:
        bundle = CachedBundle(1, "1.0", {"min.js": CachedFile("min.js", "", ["y" * 50_000])})
        out = BundleCache().read_file(bundle, "min.js")
        assert len(out) < cache_mod.MAX_LINE_CHARS + 100
        assert "line shortened, 50000 characters" in out

    def test_search_results_are_capped(self) -> None:
        bundle = CachedBundle(1, "1.0", {"a.js": CachedFile("a.js", "", ["match " + "z" * 1000] * 1000)})
        results = BundleCache().search_code(bundle, "match", max_results=10_000)
        assert len(results) == cache_mod.MAX_SEARCH_RESULTS
        assert len(results[0]["content"]) <= cache_mod.MAX_MATCH_LINE_CHARS + 4

    async def test_oversized_download_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cache_mod, "MAX_BUNDLE_BYTES", 100)
        client = MagicMock()
        client.get_bytes = AsyncMock(return_value=b"x" * 101)
        with pytest.raises(cache_mod.BundleTooLargeError):
            await BundleCache().load(client, 1, "1.0")

    async def test_oversized_extraction_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        raw = _make_tgz({"a.js": "a" * 5000, "b.js": "b" * 5000})
        monkeypatch.setattr(cache_mod, "MAX_BUNDLE_BYTES", 8000)
        client = MagicMock()
        client.get_bytes = AsyncMock(return_value=raw)
        with pytest.raises(cache_mod.BundleTooLargeError):
            await BundleCache().load(client, 1, "1.0")

    async def test_cache_is_capped_by_bytes(self) -> None:
        cache = BundleCache(max_bytes=25_000)
        client = MagicMock()
        for i in range(3):
            client.get_bytes = AsyncMock(return_value=_make_tgz({"a.js": str(i) * 5000}))
            await cache.load(client, i + 1, "1.0")
        # Each bundle counts about 10 kB; only two fit.
        assert cache.get(1, "1.0") is None
        assert cache.get(3, "1.0") is not None

    async def test_bundle_larger_than_cache_is_served_uncached(self) -> None:
        cache = BundleCache(max_bytes=1000)
        client = MagicMock()
        client.get_bytes = AsyncMock(return_value=_make_tgz({"a.js": "a" * 5000}))
        bundle = await cache.load(client, 1, "1.0")
        assert "a.js" in bundle.files
        assert cache.get(1, "1.0") is None
