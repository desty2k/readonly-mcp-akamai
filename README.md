# readonly-mcp-akamai

[![CI](https://github.com/desty2k/readonly-mcp-akamai/actions/workflows/ci.yml/badge.svg)](https://github.com/desty2k/readonly-mcp-akamai/actions)
[![codecov](https://codecov.io/gh/desty2k/readonly-mcp-akamai/graph/badge.svg)](https://codecov.io/gh/desty2k/readonly-mcp-akamai)
[![PyPI](https://img.shields.io/pypi/v/readonly-mcp-akamai)](https://pypi.org/project/readonly-mcp-akamai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Read-only MCP server for Akamai CDN. Search properties, browse EdgeWorker code, query DNS zones, inspect network lists, and translate error codes.

<!-- mcp-name: io.github.desty2k/akamai -->

> **Read-only by design.** This server can only read data. It cannot create, modify, delete, activate, deactivate, or purge anything. See [blog.wentland.io](https://blog.wentland.io) for the rationale.

## Tools

### Properties (CDN configurations)

| Tool | Description |
|------|-------------|
| `search_properties` | Fuzzy search CDN properties by name. Uses a preloaded in-memory index refreshed every 5 minutes. |
| `get_property_details` | Get property versions, hostnames, and activation status. |
| `get_property_rules` | Get the rule tree for a property version — the full CDN configuration. |
| `get_property_activations` | List deployment history for a property. |

### DNS

| Tool | Description |
|------|-------------|
| `list_dns_zones` | List all DNS zones, optionally filtered by name or type. |
| `search_dns_records` | Search DNS records within a zone by name or record type. |

### EdgeWorkers (serverless functions)

| Tool | Description |
|------|-------------|
| `list_edgeworkers` | List all EdgeWorker IDs with names and descriptions. |
| `list_edgeworker_versions` | List versions for an EdgeWorker. |
| `get_edgeworker_files` | Download a version's code bundle and list all files. Cached in memory. |
| `get_edgeworker_file` | Read a specific file from a cached bundle with line-range support. |
| `search_edgeworker_code` | Regex search across all files in a cached bundle. |

### Network Lists

| Tool | Description |
|------|-------------|
| `search_network_lists` | Search network lists (IP allowlists, blocklists, geo lists) by name. |
| `get_network_list` | Get the full contents of a network list. |

### Utility

| Tool | Description |
|------|-------------|
| `list_groups` | List account groups in the Akamai hierarchy. |
| `list_cp_codes` | List CP codes (billing/reporting identifiers) for a contract and group. |
| `translate_error_code` | Translate Akamai reference error codes to human-readable descriptions. |

## Install

```bash
# With uv (recommended)
uv pip install readonly-mcp-akamai

# With pip
pip install readonly-mcp-akamai
```

## Docker

```bash
docker run -e AKAMAI_HOST=... -e AKAMAI_CLIENT_TOKEN=... \
  -e AKAMAI_CLIENT_SECRET=... -e AKAMAI_ACCESS_TOKEN=... \
  ghcr.io/desty2k/readonly-mcp-akamai
```

## Configuration

All settings are via environment variables with the `AKAMAI_` prefix.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AKAMAI_HOST` | Yes | — | Akamai API hostname (e.g., `akab-xxxx.luna.akamaiapis.net`) |
| `AKAMAI_CLIENT_TOKEN` | Yes | — | EdgeGrid client token |
| `AKAMAI_CLIENT_SECRET` | Yes | — | EdgeGrid client secret |
| `AKAMAI_ACCESS_TOKEN` | Yes | — | EdgeGrid access token |
| `AKAMAI_TRANSPORT` | No | `stdio` | Transport: `stdio`, `http`, or `sse` |
| `AKAMAI_HTTP_PORT` | No | `8080` | Port for HTTP/SSE transport |
| `AKAMAI_LOG_FORMAT` | No | `json` | Log format: `json` or `text` |
| `AKAMAI_LOG_LEVEL` | No | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `AKAMAI_INDEX_REFRESH_INTERVAL` | No | `300` | Property index refresh interval in seconds |

Get credentials from Akamai Control Center > Identity & Access Management > API Clients.

## MCP client configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "akamai": {
      "command": "readonly-mcp-akamai",
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

```bash
claude mcp add akamai -- readonly-mcp-akamai
```

Set the `AKAMAI_*` environment variables before starting Claude Code.

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
# Clone
git clone https://github.com/desty2k/readonly-mcp-akamai.git
cd readonly-mcp-akamai

# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest --cov

# Lint
ruff check .
ruff format --check .
```

## License

MIT
