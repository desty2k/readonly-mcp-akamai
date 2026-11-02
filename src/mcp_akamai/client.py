"""Akamai API client with EdgeGrid authentication for httpx."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import uuid
from time import gmtime, strftime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import orjson

from mcp_akamai.settings import AkamaiSettings

logger = logging.getLogger(__name__)

MAX_BODY_SIZE = 131072

# The only paths the client will POST to. Each one is a read that Akamai exposes
# as POST: the error translator takes an error reference and returns what it
# means without changing anything. Any other POST is refused before a request
# is built, so the client cannot be used to change the account.
ALLOWED_POST_PATHS = frozenset({"/edge-diagnostics/v1/error-translator"})


class WriteNotAllowedError(RuntimeError):
    """Raised when code asks the client to POST to a path outside the allow-list."""


def _base64_hmac_sha256(data: str, key: str) -> str:
    return base64.b64encode(hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).digest()).decode(
        "utf-8"
    )


def _base64_sha256(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode("utf-8")


def _make_signing_key(client_secret: str, timestamp: str) -> str:
    return _base64_hmac_sha256(timestamp, client_secret)


def _make_content_hash(body: bytes | None, method: str) -> str:
    if method == "POST" and body:
        return _base64_sha256(body[:MAX_BODY_SIZE])
    return ""


def _sign_request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    client_token: str,
    client_secret: str,
    access_token: str,
) -> str:
    """Produce the EG1-HMAC-SHA256 Authorization header value."""
    timestamp = strftime("%Y%m%dT%H:%M:%S+0000", gmtime())
    nonce = str(uuid.uuid4())

    parsed = urlparse(url)
    path_with_qs = parsed.path
    if parsed.query:
        path_with_qs += "?" + parsed.query

    content_hash = _make_content_hash(body, method)

    unsigned_auth = (
        f"EG1-HMAC-SHA256 client_token={client_token};access_token={access_token};timestamp={timestamp};nonce={nonce};"
    )

    # Canonicalize headers (none needed for standard requests)
    canon_headers = ""

    data_to_sign = "\t".join(
        [
            method.upper(),
            parsed.scheme,
            parsed.hostname or "",
            path_with_qs,
            canon_headers,
            content_hash,
            unsigned_auth,
        ]
    )

    signing_key = _make_signing_key(client_secret, timestamp)
    signature = _base64_hmac_sha256(data_to_sign, signing_key)

    return f"{unsigned_auth}signature={signature}"


class AkamaiClient:
    """HTTP client for the Akamai OPEN API with EdgeGrid authentication."""

    def __init__(self, settings: AkamaiSettings) -> None:
        host = settings.host.rstrip("/")
        if not host.startswith("https://"):
            host = f"https://{host}"
        self._base_url = host
        self._client_token = settings.client_token
        self._client_secret = settings.client_secret
        self._access_token = settings.access_token
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))

    async def close(self) -> None:
        await self._http.aclose()

    def _sign(self, method: str, url: str, body: bytes | None = None) -> str:
        return _sign_request(
            method=method,
            url=url,
            headers={},
            body=body,
            client_token=self._client_token,
            client_secret=self._client_secret,
            access_token=self._access_token,
        )

    def _url(self, path: str) -> str:
        """Join an API path onto the configured host; refuse anything that leaves it."""
        url = urljoin(self._base_url + "/", path.lstrip("/"))
        if urlparse(url).netloc != urlparse(self._base_url).netloc:
            raise ValueError(f"Path resolves outside the Akamai API host: {path!r}")
        return url

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Send a GET request and return the parsed JSON response."""
        url = self._url(path)
        if params:
            # Build URL with query string for signing
            request = self._http.build_request("GET", url, params=params)
            url_with_qs = str(request.url)
        else:
            url_with_qs = url

        auth_header = self._sign("GET", url_with_qs)
        headers = {"Authorization": auth_header, "Accept": "application/json"}

        response = await self._http.get(url, params=params, headers=headers)

        if response.status_code >= 400:
            logger.warning("api_error GET %s status=%d body=%s", path, response.status_code, response.text[:500])
            response.raise_for_status()

        return orjson.loads(response.content)

    async def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        """Send a GET request and return the raw response body."""
        url = self._url(path)
        if params:
            request = self._http.build_request("GET", url, params=params)
            url_with_qs = str(request.url)
        else:
            url_with_qs = url

        auth_header = self._sign("GET", url_with_qs)
        headers = {"Authorization": auth_header, "Accept": "application/gzip"}

        response = await self._http.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.content

    async def post_json(self, path: str, body: dict[str, Any]) -> Any:
        """POST a JSON body to an allow-listed read endpoint and return the parsed response.

        Raises WriteNotAllowedError, without sending anything, for any path not in
        ALLOWED_POST_PATHS.
        """
        normalized = "/" + path.lstrip("/")
        if normalized not in ALLOWED_POST_PATHS:
            raise WriteNotAllowedError(f"POST to {path!r} is not allowed: this server only reads")
        url = self._url(normalized)
        raw_body = orjson.dumps(body)

        auth_header = self._sign("POST", url, raw_body)
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = await self._http.post(url, content=raw_body, headers=headers)

        if response.status_code >= 400:
            logger.warning("api_error POST %s status=%d body=%s", path, response.status_code, response.text[:500])
            response.raise_for_status()

        return orjson.loads(response.content)
