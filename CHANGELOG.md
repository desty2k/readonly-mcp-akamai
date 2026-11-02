# Changelog

## 0.2.0 (2026-11-02)

### Changed

- The `http` and `sse` transports listen on `127.0.0.1` by default instead of
  all interfaces. Set `AKAMAI_HTTP_HOST` to change it; any address other than
  loopback logs a warning, because these transports have no authentication.
  The Docker image sets `AKAMAI_HTTP_HOST=0.0.0.0`; publish its port on
  loopback (`-p 127.0.0.1:8080:8080`).
- The client only sends `POST` to `/edge-diagnostics/v1/error-translator`. A
  `POST` to any other path raises an error before a request is made. Tests
  check that the client has no other write method and that no other module
  sends a write.
- `search_properties` returns an object with `results`, `count` and
  `indexedProperties` instead of a bare list. It sets `ambiguous` with a note
  when the top two matches score within 5 points of each other.
- If the property index fails to load, `search_properties` returns the reason
  (rejected credentials, missing PAPI access, network error) instead of an
  empty list. A failed refresh keeps the previous index, is retried after 5,
  15, 30, 60 and then 120 seconds, and search results carry a warning until a
  load succeeds. A load where only some contract and group lists failed is
  reported the same way.
- IDs and names that go into URL paths (property, contract and group IDs, DNS
  zone, network list ID, EdgeWorker ID and version) are validated and
  percent-encoded. Values with `/`, `..` or a query string are rejected before
  any request. The client refuses paths that resolve to another host.
- Output caps: `search_dns_records` returns at most 500 records (now an object
  with `records`, `count` and `truncated`), `get_network_list` at most 5,000
  entries, `search_edgeworker_code` at most 200 matches with lines shortened to
  300 characters, and `get_edgeworker_file` at most 100,000 characters with
  lines shortened to 2,000 characters and a note with the line to continue
  from.
- The EdgeWorker bundle cache is capped by size: a bundle over 16 MB
  (compressed or extracted) is refused, and the cache holds at most 128 MB.
- MCP `serverInfo` reports the package version instead of the FastMCP version.
- Python 3.11 and 3.12 are supported; CI tests 3.11 to 3.13.
- Search queries, regex patterns and error codes are logged at `DEBUG` instead
  of `INFO`. Logging module wording no longer names specific log platforms.

## 0.1.2 (2026-11-02)

No changes to the server's behavior.

- Docker: `.dockerignore` excluded `README.md`, which the package build reads,
  so the image never built and was never published to GHCR. Fixed.
- README reworked: Quick start with `uvx`, a Credentials section (read-only API
  client), `uvx` in the client configuration, `docker run -i` for stdio, a note
  that the HTTP and SSE transports listen on all interfaces, and a comparison
  note.
- The read-only note now mentions the one `POST`, to the error translator.

## 0.1.0 (2026-04-07)

Initial release.

### Tools

- `search_properties` — fuzzy search CDN properties by name
- `get_property_details` — get property versions, hostnames, activation status
- `get_property_rules` — get the rule tree (full CDN configuration) for a property version
- `get_property_activations` — list activation/deployment history
- `list_dns_zones` — list all DNS zones
- `search_dns_records` — search DNS records within a zone
- `list_edgeworkers` — list all EdgeWorker IDs with names
- `list_edgeworker_versions` — list versions for an EdgeWorker
- `get_edgeworker_files` — download and list files in a code bundle
- `get_edgeworker_file` — read a file from a cached bundle by line range
- `search_edgeworker_code` — regex search across all files in a bundle
- `search_network_lists` — search network lists by name
- `get_network_list` — get full network list entries
- `list_groups` — list account groups
- `list_cp_codes` — list CP codes for a contract/group
- `translate_error_code` — translate Akamai error reference codes
