"""Tests for the Akamai API client and EdgeGrid signing."""

from __future__ import annotations

from mcp_akamai.client import (
    _base64_hmac_sha256,
    _base64_sha256,
    _make_content_hash,
    _make_signing_key,
    _sign_request,
)


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
