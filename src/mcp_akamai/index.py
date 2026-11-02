"""In-memory property index with fuzzy search, preloaded at startup.

The index is loaded once on startup and refreshed on a background timer. A
failed load keeps the previous contents, records the error so the search tool
can report it, and is retried with backoff instead of waiting for the next full
interval.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from rapidfuzz import fuzz, process

from mcp_akamai.client import AkamaiClient

logger = logging.getLogger(__name__)

# rapidfuzz matches below this score are dropped from results.
_SCORE_CUTOFF = 40
# The top two results are reported as ambiguous when their scores are this close.
_AMBIGUOUS_MARGIN = 5.0
# Retry delays after a failed load (seconds), capped by the refresh interval.
_RETRY_DELAYS = (5, 15, 30, 60, 120)


def _problem_detail(response: httpx.Response) -> str | None:
    """The `detail` (or `title`) of an Akamai problem+json error body, if there is one."""
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    text = body.get("detail") or body.get("title")
    return str(text)[:300] if text else None


def describe_load_error(exc: BaseException) -> str:
    """Turn a load failure into a sentence the model can relay to the user."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return "Akamai rejected the API credentials (HTTP 401). Check the AKAMAI_* credential variables."
        if status == 403:
            return "The API client cannot read Property Manager (HTTP 403). Grant it read access to PAPI."
        detail = _problem_detail(exc.response)
        return f"Akamai returned HTTP {status} while listing properties" + (f": {detail}" if detail else ".")
    if isinstance(exc, httpx.RequestError):
        return f"Cannot reach the Akamai API at AKAMAI_HOST: {type(exc).__name__}: {exc}"
    return f"{type(exc).__name__}: {exc}"


@dataclass
class PropertyEntry:
    """A property in the in-memory index."""

    property_id: str
    property_name: str
    contract_id: str
    group_id: str
    latest_version: int
    staging_version: int | None
    production_version: int | None
    asset_id: str | None


@dataclass
class PropertyIndex:
    """Preloaded index of all Akamai properties for fast fuzzy search."""

    _entries: list[PropertyEntry] = field(default_factory=list)
    _names: list[str] = field(default_factory=list)
    _loaded: bool = False
    _refresh_task: asyncio.Task[None] | None = None
    # Why the last load failed or was incomplete; None after a clean load.
    last_error: str | None = None
    last_loaded_at: float | None = None
    _failures: int = 0

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def size(self) -> int:
        return len(self._entries)

    async def load(self, client: AkamaiClient) -> bool:
        """Load all properties across all groups and contracts.

        Never raises: the server keeps running with whatever the index held
        before (empty on first load). Returns whether the load succeeded.
        """
        logger.info("index_loading_started")

        try:
            entries, failed, total, first_error = await self._fetch(client)
        except Exception as exc:  # noqa: BLE001 - any failure is reported, not raised
            self._failures += 1
            self.last_error = describe_load_error(exc)
            logger.error("index_loading_failed error=%s", self.last_error)
            return False

        if total and failed == total and first_error is not None:
            # Every property list call failed: keep the previous contents.
            self._failures += 1
            self.last_error = describe_load_error(first_error)
            logger.error("index_loading_failed error=%s", self.last_error)
            return False

        self._entries = entries
        self._names = [e.property_name for e in entries]
        self._loaded = True
        self._failures = 0
        self.last_loaded_at = time.time()
        if failed and first_error is not None:
            self.last_error = (
                f"{failed} of {total} contract/group property lists failed to load, so some properties may be "
                f"missing: {describe_load_error(first_error)}"
            )
            logger.warning("index_loading_partial count=%d failed=%d error=%s", len(entries), failed, self.last_error)
        else:
            self.last_error = None
            logger.info("index_loading_complete count=%d", len(entries))
        return True

    async def _fetch(self, client: AkamaiClient) -> tuple[list[PropertyEntry], int, int, BaseException | None]:
        """Return (entries, failed pair count, total pair count, first error)."""
        groups_data = await client.get("/papi/v1/groups")
        groups = groups_data.get("groups", {}).get("items", [])

        # Collect unique (contractId, groupId) pairs from the groups response
        pairs: list[tuple[str, str]] = []
        for group in groups:
            group_id = group.get("groupId", "")
            for contract_id in group.get("contractIds", []):
                pairs.append((contract_id, group_id))

        # Fan out requests with bounded concurrency to avoid 429s
        sem = asyncio.Semaphore(10)

        async def _fetch_pair(c: str, g: str) -> dict[str, Any]:
            async with sem:
                return await client.get("/papi/v1/properties", params={"contractId": c, "groupId": g})

        results = await asyncio.gather(*(_fetch_pair(c, g) for c, g in pairs), return_exceptions=True)

        seen_property_ids: set[str] = set()
        entries: list[PropertyEntry] = []
        failed = 0
        first_error: BaseException | None = None
        for (contract_id, group_id), result in zip(pairs, results):
            if isinstance(result, BaseException):
                failed += 1
                first_error = first_error or result
                logger.warning("property_list_error contract_id=%s group_id=%s error=%s", contract_id, group_id, result)
                continue
            properties = result.get("properties", {}).get("items", [])
            for prop in properties:
                pid = prop.get("propertyId", "")
                if pid in seen_property_ids:
                    continue
                seen_property_ids.add(pid)
                entries.append(
                    PropertyEntry(
                        property_id=pid,
                        property_name=prop.get("propertyName", ""),
                        contract_id=prop.get("contractId", ""),
                        group_id=prop.get("groupId", ""),
                        latest_version=prop.get("latestVersion", 0),
                        staging_version=prop.get("stagingVersion"),
                        production_version=prop.get("productionVersion"),
                        asset_id=prop.get("assetId"),
                    )
                )
        return entries, failed, len(pairs), first_error

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fuzzy search properties by name. Returns top matches with scores."""
        if not self._entries:
            return []

        matches = process.extract(query, self._names, scorer=fuzz.WRatio, limit=limit)
        results = []
        for name, score, idx in matches:
            if score < _SCORE_CUTOFF:
                continue
            entry = self._entries[idx]
            results.append(
                {
                    "propertyId": entry.property_id,
                    "propertyName": entry.property_name,
                    "contractId": entry.contract_id,
                    "groupId": entry.group_id,
                    "latestVersion": entry.latest_version,
                    "stagingVersion": entry.staging_version,
                    "productionVersion": entry.production_version,
                    "matchScore": round(score, 1),
                }
            )
        return results

    @staticmethod
    def is_ambiguous(results: list[dict[str, Any]]) -> bool:
        """True when the top two results score too close to pick one with confidence."""
        if len(results) < 2:
            return False
        return results[0]["matchScore"] - results[1]["matchScore"] < _AMBIGUOUS_MARGIN

    async def start_background_refresh(self, client: AkamaiClient, interval: int) -> None:
        """Start a background task that refreshes the index on a timer."""
        self._refresh_task = asyncio.create_task(self._refresh_loop(client, interval))

    def _next_delay(self, interval: int) -> float:
        if self._failures == 0:
            return interval
        return min(interval, _RETRY_DELAYS[min(self._failures, len(_RETRY_DELAYS)) - 1])

    async def _refresh_loop(self, client: AkamaiClient, interval: int) -> None:
        while True:
            await asyncio.sleep(self._next_delay(interval))
            logger.info("index_refresh_started")
            await self.load(client)

    async def stop(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
