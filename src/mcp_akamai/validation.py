"""Validation and escaping for tool arguments that end up in API URLs.

Every ID or name a tool puts into a URL path goes through one of these helpers.
Values are checked against the formats Akamai uses and rejected otherwise, then
percent-encoded, so an argument cannot add path segments (``/``, ``..``) or a
query string to the request.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from fastmcp.exceptions import ToolError

# prp_12345 or 12345 (Property Manager accepts IDs with or without the prefix).
_PROPERTY_ID_RE = re.compile(r"(prp_)?\d{1,19}")
# ctr_1-AB123, ctr_C-0N7RAC7 or the same without the prefix.
_CONTRACT_ID_RE = re.compile(r"(ctr_)?[A-Za-z0-9][A-Za-z0-9-]{0,63}")
# grp_12345 or 12345.
_GROUP_ID_RE = re.compile(r"(grp_)?\d{1,19}")
# A DNS zone name: labels of letters, digits, hyphens and underscores separated by dots.
_LABEL = r"[A-Za-z0-9_][A-Za-z0-9_-]{0,62}"
_ZONE_RE = re.compile(rf"(?=.{{1,254}}$){_LABEL}(?:\.{_LABEL})*\.?")
# Network list unique IDs, e.g. 12345_BLOCKLIST.
_NETWORK_LIST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
# EdgeWorker version identifiers, e.g. 1.0, 0.1.2, 2024-01-15.
_EW_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class InvalidArgument(ToolError):
    """A tool argument failed validation; the message is safe to show the model."""


def _check(value: str, pattern: re.Pattern[str], name: str, example: str) -> str:
    text = value.strip()
    if not pattern.fullmatch(text) or ".." in text:
        raise InvalidArgument(f"{name} must look like {example!r}, got {value!r}")
    return quote(text, safe="")


def property_id(value: str) -> str:
    return _check(value, _PROPERTY_ID_RE, "property_id", "prp_12345")


def contract_id(value: str) -> str:
    return _check(value, _CONTRACT_ID_RE, "contract_id", "ctr_1-AB123")


def group_id(value: str) -> str:
    return _check(value, _GROUP_ID_RE, "group_id", "grp_12345")


def zone(value: str) -> str:
    return _check(value, _ZONE_RE, "zone", "example.com")


def network_list_id(value: str) -> str:
    return _check(value, _NETWORK_LIST_ID_RE, "unique_id", "12345_BLOCKLIST")


def edgeworker_version(value: str) -> str:
    return _check(value, _EW_VERSION_RE, "version", "1.0")


def positive_int(value: int, name: str) -> int:
    if value < 1:
        raise InvalidArgument(f"{name} must be a positive number, got {value!r}")
    return value
