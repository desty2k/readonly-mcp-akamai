# readonly-mcp-akamai

[![CI](https://github.com/desty2k/readonly-mcp-akamai/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/desty2k/readonly-mcp-akamai/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/desty2k/readonly-mcp-akamai/graph/badge.svg)](https://codecov.io/gh/desty2k/readonly-mcp-akamai)
[![PyPI](https://img.shields.io/pypi/v/readonly-mcp-akamai.svg)](https://pypi.org/project/readonly-mcp-akamai/)
[![Python](https://img.shields.io/pypi/pyversions/readonly-mcp-akamai.svg)](https://pypi.org/project/readonly-mcp-akamai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A read-only Model Context Protocol (MCP) server that lets AI agents explore an
Akamai account: CDN properties and their rule trees, EdgeWorker code, Edge DNS
zones, network lists, CP codes, and error references. 16 tools, all of them
reads.

## Quick start

With [uv](https://docs.astral.sh/uv/) installed, there is nothing else to install:

```bash
claude mcp add akamai \
  -e AKAMAI_HOST=akab-xxxx.luna.akamaiapis.net \
  -e AKAMAI_CLIENT_TOKEN=akab-xxxx \
  -e AKAMAI_CLIENT_SECRET=xxxx \
  -e AKAMAI_ACCESS_TOKEN=akab-xxxx \
  -- uvx readonly-mcp-akamai
```

`uvx` downloads the package into a cached, isolated environment and runs it.
Python 3.11 or newer.

<!-- mcp-name: io.github.desty2k/akamai -->

> **Read-only by design.** Every call this server makes reads. It uses `GET`,
> plus one `POST` to Akamai's error translator, which takes an error reference
> and returns what it means without changing anything. The client refuses a
> `POST` to any other path before sending it, and a test checks that. It cannot
> create, modify, delete, activate, deactivate, or purge anything. Give the API client
> read-only access as a second line of defense: see [Credentials](#credentials).
> Read [why I build read-only MCP servers](https://blog.wentland.io/blog/why-read-only-mcp/).

## Credentials

Create an API client in Akamai Control Center under **Identity & Access
Management → API clients**. Grant read-only access, where the API offers it, to
the APIs the tools use:

| API | Used by |
|---|---|
| Property Manager (PAPI) | properties, groups, CP codes |
| Edge DNS | DNS tools |
| EdgeWorkers | EdgeWorker tools |
| Network Lists | network list tools |
| Edge Diagnostics | `translate_error_code` |

The client's `host`, `client_token`, `client_secret` and `access_token` map to
the four `AKAMAI_*` variables below.

## Tools

### Properties (CDN configurations)

| Tool | Description |
|------|-------------|
| `search_properties` | Fuzzy search CDN properties by name. Uses a preloaded in-memory index refreshed every 5 minutes. Returns match scores, flags close matches, and reports why the index failed to load if it did. |
| `get_property_details` | Get property versions, hostnames, and activation status. |
| `get_property_rules` | Get the rule tree for a property version — the full CDN configuration. |
| `get_property_activations` | List deployment history for a property. |

### DNS

| Tool | Description |
|------|-------------|
| `list_dns_zones` | List all DNS zones, optionally filtered by name or type. |
| `search_dns_records` | Search DNS records within a zone by name or record type. Returns at most 500 records. |

### EdgeWorkers (serverless functions)

| Tool | Description |
|------|-------------|
| `list_edgeworkers` | List all EdgeWorker IDs with names and descriptions. |
| `list_edgeworker_versions` | List versions for an EdgeWorker. |
| `get_edgeworker_files` | Download a version's code bundle and list all files. Cached in memory (bundles up to 16 MB, 128 MB in total). |
| `get_edgeworker_file` | Read a specific file from a cached bundle with line-range support. Output is capped at 100,000 characters, with the line to continue from. |
| `search_edgeworker_code` | Regex search across all files in a cached bundle. Returns at most 200 matches. |

### Network Lists

| Tool | Description |
|------|-------------|
| `search_network_lists` | Search network lists (IP allowlists, blocklists, geo lists) by name. |
| `get_network_list` | Get the contents of a network list, at most 5,000 entries. |

### Utility

| Tool | Description |
|------|-------------|
| `list_groups` | List account groups in the Akamai hierarchy. |
| `list_cp_codes` | List CP codes (billing/reporting identifiers) for a contract and group. |
| `translate_error_code` | Translate Akamai reference error codes to human-readable descriptions. |

## Install

```bash
uv tool install readonly-mcp-akamai   # or: pip install readonly-mcp-akamai
```

Not needed for the Quick start, which runs it with `uvx`.

## Docker

```bash
docker run -i --rm \
  -e AKAMAI_HOST=akab-xxxx.luna.akamaiapis.net \
  -e AKAMAI_CLIENT_TOKEN=akab-xxxx \
  -e AKAMAI_CLIENT_SECRET=xxxx \
  -e AKAMAI_ACCESS_TOKEN=akab-xxxx \
  ghcr.io/desty2k/readonly-mcp-akamai:latest
```

`-i` keeps stdin open for the default stdio transport.

## Configuration

All settings are environment variables with the `AKAMAI_` prefix.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AKAMAI_HOST` | Yes | — | Akamai API hostname (e.g., `akab-xxxx.luna.akamaiapis.net`) |
| `AKAMAI_CLIENT_TOKEN` | Yes | — | EdgeGrid client token |
| `AKAMAI_CLIENT_SECRET` | Yes | — | EdgeGrid client secret |
| `AKAMAI_ACCESS_TOKEN` | Yes | — | EdgeGrid access token |
| `AKAMAI_TRANSPORT` | No | `stdio` | Transport: `stdio`, `http`, or `sse` |
| `AKAMAI_HTTP_HOST` | No | `127.0.0.1` | Address the HTTP/SSE transport listens on |
| `AKAMAI_HTTP_PORT` | No | `8080` | Port for HTTP/SSE transport |
| `AKAMAI_LOG_FORMAT` | No | `json` | Log format: `json` or `text` |
| `AKAMAI_LOG_LEVEL` | No | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `AKAMAI_INDEX_REFRESH_INTERVAL` | No | `300` | Property index refresh interval in seconds |

The `http` and `sse` transports have no authentication: anyone who can reach
the port can read the Akamai account with the configured credentials. They
listen on `127.0.0.1` by default. Setting `AKAMAI_HTTP_HOST` to any other
address logs a warning at startup. The Docker image sets
`AKAMAI_HTTP_HOST=0.0.0.0` so a published port works; publish it on loopback
only:

```bash
docker run --rm -p 127.0.0.1:8080:8080 -e AKAMAI_TRANSPORT=http \
  -e AKAMAI_HOST=... -e AKAMAI_CLIENT_TOKEN=... \
  -e AKAMAI_CLIENT_SECRET=... -e AKAMAI_ACCESS_TOKEN=... \
  ghcr.io/desty2k/readonly-mcp-akamai:latest
```

## MCP client configuration

### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on
macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "akamai": {
      "command": "uvx",
      "args": ["readonly-mcp-akamai"],
      "env": {
        "AKAMAI_HOST": "akab-xxxx.luna.akamaiapis.net",
        "AKAMAI_CLIENT_TOKEN": "akab-xxxx",
        "AKAMAI_CLIENT_SECRET": "xxxx",
        "AKAMAI_ACCESS_TOKEN": "akab-xxxx"
      }
    }
  }
}
```

### Claude Code

See [Quick start](#quick-start).

## How it compares

As of November 2026. Akamai's own MCP servers under
[akamai-developers](https://github.com/orgs/akamai-developers/repositories)
cover other products: [Akamai Cloud](https://github.com/akamai-developers/akamai-cloud-mcp)
(Linode, also read-only), Akamai Functions, and the documentation. None of them
reads Property Manager, EdgeWorkers, Edge DNS, or Network Lists. Check the
projects themselves before relying on this.

## Example questions

An agent with this server can answer:

- "Find the CDN property for api.example.com and show me its caching rules"
- "What version is currently deployed to production for the main website?"
- "Show me all DNS records for example.com"
- "What EdgeWorkers are configured? Show me the code for the request router"
- "Search for all uses of `setResponseHeader` in EdgeWorker 42"
- "What IPs are in the blocklist network list?"
- "Translate this Akamai error: 9.6f64d440.1318965461.2f2b078"
- "List all CP codes for the main contract"

## Development

```bash
git clone https://github.com/desty2k/readonly-mcp-akamai
cd readonly-mcp-akamai
uv sync --extra dev
uv run pytest --cov
uv run ruff check .
uv run ruff format --check .
```

## License

MIT — see [LICENSE](LICENSE).
