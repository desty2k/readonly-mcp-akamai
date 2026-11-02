"""Tests for the Akamai API client and EdgeGrid signing."""

from __future__ import annotations

import pathlib
import re

import httpx
import pytest
import respx

from mcp_akamai.client import (
    ALLOWED_POST_PATHS,
    AkamaiClient,
    WriteNotAllowedError,
    _base64_hmac_sha256,
    _base64_sha256,
    _make_content_hash,
    _make_signing_key,
    _sign_request,
)
from mcp_akamai.settings import AkamaiSettings


class TestEdgeGridSigning:
    def test_base64_sha256(self) -> None:
        result = _base64_sha256(b"hello")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_base64_hmac_sha256(self) -> None:
        result = _base64_hmac_sha256("data", "key")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_make_signing_key(self) -> None:
        secret = "test-secret"
        timestamp = "20250101T00:00:00+0000"
        key = _make_signing_key(secret, timestamp)
        assert isinstance(key, str)
        assert len(key) > 0

    def test_content_hash_get_request(self) -> None:
        result = _make_content_hash(None, "GET")
        assert result == ""

    def test_content_hash_post_request(self) -> None:
        result = _make_content_hash(b'{"key": "value"}', "POST")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_content_hash_empty_post(self) -> None:
        result = _make_content_hash(None, "POST")
        assert result == ""

    def test_sign_request_produces_header(self) -> None:
        secret = "test-secret"
        header = _sign_request(
            method="GET",
            url="https://test.akamaiapis.net/papi/v1/groups",
            headers={},
            body=None,
            client_token="test-ct",
            client_secret=secret,
            access_token="test-at",
        )
        assert header.startswith("EG1-HMAC-SHA256")
        assert "client_token=test-ct" in header
        assert "access_token=test-at" in header
        assert "signature=" in header

    def test_sign_request_with_query_string(self) -> None:
        secret = "test-secret"
        header = _sign_request(
            method="GET",
            url="https://test.akamaiapis.net/papi/v1/properties?contractId=ctr_1&groupId=grp_1",
            headers={},
            body=None,
            client_token="ct",
            client_secret=secret,
            access_token="at",
        )
        assert "signature=" in header

    def test_sign_request_post(self) -> None:
        secret = "test-secret"
        body = b'{"errorCode": "9.abc.123"}'
        header = _sign_request(
            method="POST",
            url="https://test.akamaiapis.net/edge-diagnostics/v1/error-translator",
            headers={},
            body=body,
            client_token="ct",
            client_secret=secret,
            access_token="at",
        )
        assert header.startswith("EG1-HMAC-SHA256")
        assert "signature=" in header

    def test_different_urls_produce_different_signatures(self) -> None:
        secret = "test-secret"
        h1 = _sign_request(
            method="GET",
            url="https://test.akamaiapis.net/papi/v1/groups",
            headers={},
            body=None,
            client_token="ct",
            client_secret=secret,
            access_token="at",
        )
        h2 = _sign_request(
            method="GET",
            url="https://test.akamaiapis.net/papi/v1/contracts",
            headers={},
            body=None,
            client_token="ct",
            client_secret=secret,
            access_token="at",
        )
        # Signatures should differ (different paths, and timestamps/nonces are unique)
        sig1 = h1.split("signature=")[1]
        sig2 = h2.split("signature=")[1]
        assert sig1 != sig2


# --- read-only guarantee ---------------------------------------------------


@pytest.fixture
def client(settings: AkamaiSettings) -> AkamaiClient:
    return AkamaiClient(settings)


def test_client_exposes_only_read_methods() -> None:
    """The client's public surface is reads plus the allow-listed POST; a new write method must fail this test."""
    public = {name for name in dir(AkamaiClient) if not name.startswith("_")}
    assert public == {"get", "get_bytes", "post_json", "close"}


def test_post_allow_list_is_only_the_error_translator() -> None:
    assert ALLOWED_POST_PATHS == frozenset({"/edge-diagnostics/v1/error-translator"})


@pytest.mark.parametrize(
    "path",
    [
        "/papi/v1/properties/prp_1/activations",
        "/ccu/v3/invalidate/url/production",
        "/edge-diagnostics/v1/error-translator/../../papi/v1/properties",
        "/edge-diagnostics/v1/error-translator?x=1",
        "/edge-diagnostics/v1/",
        "https://evil.example.com/edge-diagnostics/v1/error-translator",
    ],
)
@respx.mock
async def test_post_to_other_paths_is_rejected_without_a_request(client: AkamaiClient, path: str) -> None:
    route = respx.route().mock(return_value=httpx.Response(200, json={}))
    try:
        with pytest.raises(WriteNotAllowedError):
            await client.post_json(path, body={"x": 1})
    finally:
        await client.close()
    assert route.call_count == 0


@respx.mock
async def test_post_to_error_translator_is_sent(client: AkamaiClient) -> None:
    route = respx.post("https://test.akamaiapis.net/edge-diagnostics/v1/error-translator").mock(
        return_value=httpx.Response(200, json={"translatedError": {}})
    )
    try:
        await client.post_json("edge-diagnostics/v1/error-translator", body={"errorCode": "9.1.2.3"})
    finally:
        await client.close()
    assert route.call_count == 1


@respx.mock
async def test_reads_send_only_get(client: AkamaiClient) -> None:
    route = respx.route(host="test.akamaiapis.net").mock(return_value=httpx.Response(200, json={}))
    try:
        await client.get("/papi/v1/groups")
        await client.get_bytes("/edgeworkers/v1/ids/1/versions/1.0/content")
    finally:
        await client.close()
    assert {call.request.method for call in route.calls} == {"GET"}


async def test_get_refuses_a_path_that_leaves_the_api_host(client: AkamaiClient) -> None:
    try:
        with pytest.raises(ValueError, match="outside the Akamai API host"):
            await client.get("https://evil.example.com/papi/v1/groups")
    finally:
        await client.close()


def test_tools_reach_akamai_only_through_the_client() -> None:
    """No module sends a write verb except the client's allow-listed post_json."""
    src = pathlib.Path(__file__).parents[1] / "src" / "mcp_akamai"
    write_call = re.compile(r"\.(post|put|patch|delete)\(|\"(POST|PUT|PATCH|DELETE)\"", re.IGNORECASE)
    offenders = []
    for path in src.rglob("*.py"):
        text = path.read_text()
        if path.name != "client.py" and write_call.search(text):
            offenders.append(path.name)
        if path.parent.name == "tools" and "httpx" in text:
            offenders.append(path.name)
    assert offenders == []
