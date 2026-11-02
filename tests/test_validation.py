"""Tests for validation of arguments that end up in API URLs."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from helpers import extract_tools

from mcp_akamai import validation as v
from mcp_akamai.tools import dns, edgeworkers, network_lists, properties


@pytest.mark.parametrize(
    ("fn", "value"),
    [
        (v.property_id, "prp_12345"),
        (v.property_id, "12345"),
        (v.contract_id, "ctr_1-AB123"),
        (v.contract_id, "ctr_C-0N7RAC7"),
        (v.group_id, "grp_12345"),
        (v.zone, "example.com"),
        (v.zone, "example.com."),
        (v.zone, "_dmarc.example.co.uk"),
        (v.zone, "1.168.192.in-addr.arpa"),
        (v.network_list_id, "12345_BLOCKLIST"),
        (v.edgeworker_version, "1.0"),
        (v.edgeworker_version, "0.1.2-beta"),
    ],
)
def test_accepts_valid_values(fn, value: str) -> None:
    assert fn(value) == value


@pytest.mark.parametrize(
    ("fn", "value"),
    [
        (v.property_id, "prp_1/../../groups"),
        (v.property_id, "prp_1?x=1"),
        (v.contract_id, "ctr_1/x"),
        (v.group_id, "grp_abc"),
        (v.zone, "../zones"),
        (v.zone, "example..com"),
        (v.zone, "example.com/recordsets"),
        (v.zone, ""),
        (v.network_list_id, "123/../456"),
        (v.network_list_id, "123%2F456"),
        (v.edgeworker_version, ".."),
        (v.edgeworker_version, "1..0"),
        (v.edgeworker_version, "1.0/../../2"),
    ],
)
def test_rejects_values_that_change_the_url(fn, value: str) -> None:
    with pytest.raises(v.InvalidArgument):
        fn(value)


def test_rejects_non_positive_numbers() -> None:
    with pytest.raises(v.InvalidArgument):
        v.positive_int(0, "edgeworker_id")


@pytest.mark.parametrize(
    ("module", "tool", "kwargs"),
    [
        (properties, "get_property_details", {"property_id": "../x", "contract_id": "ctr_1", "group_id": "grp_1"}),
        (
            properties,
            "get_property_rules",
            {"property_id": "prp_1", "version": -1, "contract_id": "ctr_1", "group_id": "grp_1"},
        ),
        (properties, "get_property_activations", {"property_id": "prp_1", "contract_id": "c/1", "group_id": "grp_1"}),
        (dns, "search_dns_records", {"zone": "../../zones"}),
        (network_lists, "get_network_list", {"unique_id": "1/../2"}),
        (edgeworkers, "list_edgeworker_versions", {"edgeworker_id": -1}),
        (edgeworkers, "get_edgeworker_files", {"edgeworker_id": 1, "version": "../1"}),
    ],
)
async def test_tools_reject_bad_ids_before_calling_akamai(mock_ctx: MagicMock, module, tool: str, kwargs) -> None:
    tools = extract_tools(module)
    with pytest.raises(v.InvalidArgument):
        await tools[tool](mock_ctx, **kwargs)
    client = mock_ctx.lifespan_context.client
    client.get.assert_not_called()
    client.get_bytes.assert_not_called()
