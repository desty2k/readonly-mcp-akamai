# Changelog

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
