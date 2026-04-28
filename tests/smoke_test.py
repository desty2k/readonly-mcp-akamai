"""Smoke tests against the real Akamai API. Requires .env credentials.

Run manually: uv run python tests/smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Load .env from project root
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from mcp_akamai.client import AkamaiClient
from mcp_akamai.cache import BundleCache
from mcp_akamai.index import PropertyIndex
from mcp_akamai.settings import AkamaiSettings

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"


async def run() -> int:
    settings = AkamaiSettings()  # type: ignore[call-arg]
    client = AkamaiClient(settings)
    failures = 0

    try:
        # --- Groups ---
        print("list_groups ... ", end="", flush=True)
        groups = await client.get("/papi/v1/groups")
        items = groups.get("groups", {}).get("items", [])
        assert len(items) > 0, "no groups returned"
        print(f"{PASS} ({len(items)} groups)")

        first_group = items[0]
        group_id = first_group["groupId"]
        contract_ids = first_group.get("contractIds", [])
        contract_id = contract_ids[0] if contract_ids else None

        # --- Property index ---
        print("property_index.load ... ", end="", flush=True)
        index = PropertyIndex()
        await index.load(client)
        assert index.loaded, "index did not load"
        assert index.size > 0, "index is empty"
        print(f"{PASS} ({index.size} properties)")

        # --- Property search ---
        print("property_index.search ... ", end="", flush=True)
        results = index.search("example", limit=5)
        # May or may not find matches depending on account, just check it doesn't crash
        print(f"{PASS} ({len(results)} matches)")

        # --- Property details (use first indexed property) ---
        if index._entries:
            entry = index._entries[0]
            print(f"get_property_details ({entry.property_name}) ... ", end="", flush=True)
            prop_data = await client.get(
                f"/papi/v1/properties/{entry.property_id}",
                params={"contractId": entry.contract_id, "groupId": entry.group_id},
            )
            prop_items = prop_data.get("properties", {}).get("items", [])
            assert len(prop_items) > 0, "property not found"
            print(f"{PASS}")

            # --- Property rules ---
            print(f"get_property_rules (v{entry.latest_version}) ... ", end="", flush=True)
            rules_data = await client.get(
                f"/papi/v1/properties/{entry.property_id}/versions/{entry.latest_version}/rules",
                params={"contractId": entry.contract_id, "groupId": entry.group_id},
            )
            assert "rules" in rules_data, "no rules in response"
            print(f"{PASS}")

            # --- Property activations ---
            print(f"get_property_activations ... ", end="", flush=True)
            act_data = await client.get(
                f"/papi/v1/properties/{entry.property_id}/activations",
                params={"contractId": entry.contract_id, "groupId": entry.group_id},
            )
            act_items = act_data.get("activations", {}).get("items", [])
            print(f"{PASS} ({len(act_items)} activations)")

            # --- Hostnames ---
            print(f"get_property_hostnames (v{entry.latest_version}) ... ", end="", flush=True)
            host_data = await client.get(
                f"/papi/v1/properties/{entry.property_id}/versions/{entry.latest_version}/hostnames",
                params={"contractId": entry.contract_id, "groupId": entry.group_id},
            )
            hostnames = host_data.get("hostnames", {}).get("items", [])
            print(f"{PASS} ({len(hostnames)} hostnames)")
        else:
            print(f"get_property_details ... {SKIP} (no properties in index)")

        # --- CP codes ---
        if contract_id:
            print(f"list_cp_codes ... ", end="", flush=True)
            cp_data = await client.get(
                "/papi/v1/cpcodes",
                params={"contractId": contract_id, "groupId": group_id},
            )
            cpcodes = cp_data.get("cpcodes", {}).get("items", [])
            print(f"{PASS} ({len(cpcodes)} cp codes)")
        else:
            print(f"list_cp_codes ... {SKIP} (no contract)")

        # --- DNS zones ---
        print("list_dns_zones ... ", end="", flush=True)
        try:
            dns_data = await client.get("/config-dns/v2/zones", params={"showAll": "true"})
            zones = dns_data.get("zones", [])
            print(f"{PASS} ({len(zones)} zones)")

            if zones:
                zone_name = zones[0].get("zone")
                print(f"search_dns_records ({zone_name}) ... ", end="", flush=True)
                rec_data = await client.get(
                    f"/config-dns/v2/zones/{zone_name}/recordsets",
                    params={"showAll": "true"},
                )
                records = rec_data.get("recordsets", [])
                print(f"{PASS} ({len(records)} records)")
        except Exception as e:
            print(f"{FAIL} {e}")
            failures += 1

        # --- Network lists ---
        print("search_network_lists ... ", end="", flush=True)
        try:
            nl_data = await client.get(
                "/network-list/v2/network-lists",
                params={"includeElements": "false"},
            )
            lists = nl_data.get("networkLists", [])
            print(f"{PASS} ({len(lists)} lists)")

            if lists:
                nl_id = lists[0].get("uniqueId")
                print(f"get_network_list ({nl_id}) ... ", end="", flush=True)
                detail = await client.get(
                    f"/network-list/v2/network-lists/{nl_id}",
                    params={"includeElements": "true"},
                )
                elem_count = detail.get("elementCount", 0)
                print(f"{PASS} ({elem_count} elements)")
        except Exception as e:
            print(f"{FAIL} {e}")
            failures += 1

        # --- EdgeWorkers ---
        print("list_edgeworkers ... ", end="", flush=True)
        try:
            ew_data = await client.get("/edgeworkers/v1/ids")
            ew_items = ew_data.get("edgeWorkerIds", [])
            print(f"{PASS} ({len(ew_items)} edgeworkers)")

            if ew_items:
                ew_id = ew_items[0]["edgeWorkerId"]
                ew_name = ew_items[0].get("name", "?")

                print(f"list_edgeworker_versions ({ew_name}) ... ", end="", flush=True)
                ver_data = await client.get(f"/edgeworkers/v1/ids/{ew_id}/versions")
                versions = ver_data.get("versions", [])
                print(f"{PASS} ({len(versions)} versions)")

                if versions:
                    ver = versions[0]["version"]
                    print(f"bundle_cache.load ({ew_name} v{ver}) ... ", end="", flush=True)
                    cache = BundleCache()
                    bundle = await cache.load(client, ew_id, ver)
                    files = cache.list_files(bundle)
                    print(f"{PASS} ({len(files)} files)")

                    if files:
                        first_file = files[0]["path"]
                        print(f"bundle_cache.read_file ({first_file}) ... ", end="", flush=True)
                        content = cache.read_file(bundle, first_file, 1, 5)
                        assert len(content) > 0, "empty file content"
                        print(f"{PASS}")

                        print(f"bundle_cache.search_code ('function') ... ", end="", flush=True)
                        matches = cache.search_code(bundle, "function")
                        print(f"{PASS} ({len(matches)} matches)")
        except Exception as e:
            print(f"{FAIL} {e}")
            failures += 1

    except Exception as e:
        print(f"{FAIL} {e}")
        failures += 1
    finally:
        await client.close()

    print()
    if failures:
        print(f"\033[91m{failures} failure(s)\033[0m")
    else:
        print("\033[92mAll smoke tests passed\033[0m")
    return failures


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
