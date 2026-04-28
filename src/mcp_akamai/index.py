"""In-memory property index with fuzzy search, preloaded at startup."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz, process

from mcp_akamai.client import AkamaiClient

logger = logging.getLogger(__name__)


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

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def size(self) -> int:
        return len(self._entries)

    async def load(self, client: AkamaiClient) -> None:
        """Load all properties across all groups and contracts."""
        logger.info("loading_started")

        try:
            groups_data = await client.get("/papi/v1/groups")
            groups = groups_data.get("groups", {}).get("items", [])

            seen_property_ids: set[str] = set()
            entries: list[PropertyEntry] = []

            # Collect unique (contractId, groupId) pairs from the groups response
            pairs: list[tuple[str, str]] = []
            for group in groups:
                group_id = group.get("groupId", "")
                for contract_id in group.get("contractIds", []):
                    pairs.append((contract_id, group_id))

            # Fan out requests with bounded concurrency to avoid 429s
            sem = asyncio.Semaphore(10)

            async def _fetch(c: str, g: str) -> dict[str, Any]:
                async with sem:
                    return await client.get("/papi/v1/properties", params={"contractId": c, "groupId": g})

            tasks = [_fetch(c, g) for c, g in pairs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning("property_list_error error=%s", result)
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

            self._entries = entries
            self._names = [e.property_name for e in entries]
            self._loaded = True
            logger.info("loading_complete count=%d", len(entries))

        except Exception:
            logger.exception("loading_failed")

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Fuzzy search properties by name. Returns top matches with scores."""
        if not self._entries:
            return []

        matches = process.extract(query, self._names, scorer=fuzz.WRatio, limit=limit)
        results = []
        for name, score, idx in matches:
            if score < 40:
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

    async def start_background_refresh(self, client: AkamaiClient, interval: int) -> None:
        """Start a background task that refreshes the index on a timer."""
        self._refresh_task = asyncio.create_task(self._refresh_loop(client, interval))

    async def _refresh_loop(self, client: AkamaiClient, interval: int) -> None:
        while True:
            await asyncio.sleep(interval)
            logger.info("index_refresh_started")
            await self.load(client)

    async def stop(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
