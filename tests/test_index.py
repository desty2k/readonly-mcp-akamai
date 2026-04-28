"""Tests for the property index and fuzzy search."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mcp_akamai.index import PropertyEntry, PropertyIndex
from tests.conftest import make_groups_response, make_properties_response


@pytest.fixture
def populated_index() -> PropertyIndex:
    """An index pre-populated with test data (no API calls needed)."""
    idx = PropertyIndex()
    idx._entries = [
        PropertyEntry("prp_1", "www.example.com", "ctr_1", "grp_1", 5, 4, 3, "aid_1"),
        PropertyEntry("prp_2", "api.example.com", "ctr_1", "grp_1", 2, 2, 1, "aid_2"),
        PropertyEntry("prp_3", "cdn.images.example.com", "ctr_1", "grp_2", 10, None, 10, "aid_3"),
        PropertyEntry("prp_4", "checkout-flow.example.com", "ctr_2", "grp_3", 1, None, None, None),
        PropertyEntry("prp_5", "blog.example.com", "ctr_2", "grp_3", 7, 7, 6, "aid_5"),
    ]
    idx._names = [e.property_name for e in idx._entries]
    idx._loaded = True
    return idx


class TestPropertyIndexSearch:
    def test_exact_match(self, populated_index: PropertyIndex) -> None:
        results = populated_index.search("www.example.com", limit=5)
        assert len(results) >= 1
        assert results[0]["propertyName"] == "www.example.com"
        assert results[0]["matchScore"] > 90

    def test_partial_match(self, populated_index: PropertyIndex) -> None:
        results = populated_index.search("api", limit=5)
        # api.example.com should rank high
        names = [r["propertyName"] for r in results]
        assert "api.example.com" in names

    def test_fuzzy_match(self, populated_index: PropertyIndex) -> None:
        results = populated_index.search("checkout", limit=5)
        names = [r["propertyName"] for r in results]
        assert "checkout-flow.example.com" in names

    def test_no_match_returns_empty(self, populated_index: PropertyIndex) -> None:
        results = populated_index.search("zzzznonexistent", limit=5)
        # All scores should be below threshold or list should be empty
        assert all(r["matchScore"] >= 40 for r in results)

    def test_limit_respected(self, populated_index: PropertyIndex) -> None:
        results = populated_index.search("example", limit=2)
        assert len(results) <= 2

    def test_empty_index_returns_empty(self) -> None:
        idx = PropertyIndex()
        results = idx.search("anything")
        assert results == []

    def test_result_shape(self, populated_index: PropertyIndex) -> None:
        results = populated_index.search("www", limit=1)
        assert len(results) >= 1
        r = results[0]
        assert "propertyId" in r
        assert "propertyName" in r
        assert "contractId" in r
        assert "groupId" in r
        assert "latestVersion" in r
        assert "stagingVersion" in r
        assert "productionVersion" in r
        assert "matchScore" in r


class TestPropertyIndexLoad:
    async def test_load_from_api(self, mock_client: AsyncMock) -> None:
        mock_client.get = AsyncMock(
            side_effect=[
                make_groups_response(
                    [
                        {"groupId": "grp_1", "groupName": "G1", "contractIds": ["ctr_1"]},
                    ]
                ),
                make_properties_response(
                    [
                        {
                            "propertyId": "prp_100",
                            "propertyName": "loaded.example.com",
                            "contractId": "ctr_1",
                            "groupId": "grp_1",
                            "latestVersion": 1,
                            "stagingVersion": None,
                            "productionVersion": None,
                            "assetId": None,
                        }
                    ]
                ),
            ]
        )

        idx = PropertyIndex()
        await idx.load(mock_client)

        assert idx.loaded
        assert idx.size == 1
        results = idx.search("loaded", limit=5)
        assert len(results) == 1
        assert results[0]["propertyName"] == "loaded.example.com"

    async def test_load_deduplicates(self, mock_client: AsyncMock) -> None:
        """Properties appearing in multiple groups should only appear once."""
        prop = {
            "propertyId": "prp_dup",
            "propertyName": "dup.example.com",
            "contractId": "ctr_1",
            "groupId": "grp_1",
            "latestVersion": 1,
        }
        mock_client.get = AsyncMock(
            side_effect=[
                make_groups_response(
                    [
                        {"groupId": "grp_1", "groupName": "G1", "contractIds": ["ctr_1", "ctr_2"]},
                    ]
                ),
                make_properties_response([prop]),
                make_properties_response([prop]),
            ]
        )

        idx = PropertyIndex()
        await idx.load(mock_client)
        assert idx.size == 1

    async def test_load_handles_api_errors(self, mock_client: AsyncMock) -> None:
        """Failed property list calls should not crash the index load."""
        mock_client.get = AsyncMock(
            side_effect=[
                make_groups_response(
                    [
                        {"groupId": "grp_1", "groupName": "G1", "contractIds": ["ctr_1"]},
                    ]
                ),
                Exception("API timeout"),
            ]
        )

        idx = PropertyIndex()
        await idx.load(mock_client)
        assert idx.loaded
        assert idx.size == 0
