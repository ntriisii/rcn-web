from rcn_web.storage.utils import get_uniq_apps
import os
import asyncio
import aiohttp
import time
from urllib.parse import urlparse

from rcn_core.data_access import (
    get_storage,
    get_unprocessed_entries,
)
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.utils import (
    web_match_storage,
    is_in_scope,
    RemoteFlowsAdapter,
)
from rcn_core.decorators import rcn_event
from rcn_core.log import rlog

from rcn_web.core.js_utils import (
    get_js_hash,
    is_third_party,
)


@rcn_event()
async def js_intelligence_monitor(event, scheduled_md):
    """
    Simplified monitor: tracks JS file hashes only.
    """
    scanner_name = event["name"]
    async with get_unprocessed_entries(
        scanner_name, event, match_storage_fn=web_match_storage
    ) as unscanned:
        if not unscanned:
            return

        # Group by app
        app_js_map = {}
        for item in unscanned.values():
            app = item["parent"]
            if app["id"] not in app_js_map:
                app_js_map[app["id"]] = {"app": app, "links": []}
            app_js_map[app["id"]]["links"].append(item["entry"])

        semaphore = asyncio.Semaphore(10)
        async with aiohttp.ClientSession() as session:
            for app_id, data in app_js_map.items():
                app = data["app"]
                links_tasks = [
                    handle_monitor_js_hash(session, semaphore, app, js_link)
                    for js_link in data["links"]
                ]
                results = await asyncio.gather(*links_tasks)

                inventory_entries = [r for r in results if r is not None]
                if inventory_entries:
                    js_inventory_list = get_storage_create(
                        "web-apps::js-inventory", parent_id=app_id
                    )
                    if js_inventory_list:
                        js_inventory = js_inventory_list[0]
                        js_inventory.add_many(inventory_entries, source="js_monitor")


async def handle_monitor_js_hash(session, semaphore, app, js_link):
    url = js_link.get("url")
    if not url:
        return None

    # Only analyze if the domain is in scope
    domain = urlparse(url).netloc
    if not is_in_scope(domain):
        return None

    async with semaphore:
        try:
            content = None
            flow_id = js_link.get("flow-id")

            # Try to fetch content from the flows adapter first
            if flow_id:
                adapter = RemoteFlowsAdapter.get_instance()
                flows = await adapter.get_flows_by_id([flow_id])
                if flows:
                    content = flows[0].get("response-body")

            if not content:
                try:
                    async with session.get(url, timeout=15) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                except:
                    pass

            if not content:
                return None

            current_hash = await get_js_hash(content)
            js_inventory_list = get_storage_create(
                "web-apps::js-inventory", parent_id=app["id"]
            )

            if not js_inventory_list:
                return None

            # Check inventory
            existing = js_inventory_list[0].get_filtered(f"url = '{url}'")
            is_changed = True
            if existing:
                if existing[0].get("hash") == current_hash:
                    is_changed = False

            if is_changed:
                rlog(f"JS Hash changed for {url}")
                return {
                    "url": url,
                    "hash": current_hash,
                    "flow-id": str(flow_id) if flow_id else None,
                    "last_seen": time.time(),
                    "is_third_party": is_third_party(url, content),
                    "status": "monitored",
                }

        except Exception as e:
            rlog(f"Error monitoring hash for {url}: {e}", level="debug")

    return None


# --- LEGACY CODE BACKUP (Currently Disabled) ---
"""
async def process_js_file(app, url, content, content_hash, project_name="default_target", nuclei_findings=None):
    # Core pipeline for a single JS file.
    if nuclei_findings is None:
        nuclei_findings = []
    rlog(f"Processing JS file: {url}")

    # 1. Recovery/Deobfuscation
    # Primary: deobfuscate the current content
    unpacked_path, deobf_success = await deobfuscate_js(content, url)

    # 2. Tools Analysis
    all_findings = []

    # Semgrep - Run on the unpacked source
    semgrep_findings = await run_semgrep(unpacked_path)
    for f in semgrep_findings:
        all_findings.append({
            "type": "semgrep",
            "rule": f.get("check_id"),
            "location": f.get("path"),
            "line": f.get("start", {}).get("line"),
            "evidence": f.get("extra", {}).get("lines"),
            "severity": f.get("extra", {}).get("severity"),
        })

    # jsluice (run on all files in unpacked_path)
    for root, dirs, files in os.walk(unpacked_path):
        for file in files:
            if file.endswith(".js"):
                fpath = os.path.join(root, file)
                jsluice_findings = await run_jsluice(fpath)
                for jf in jsluice_findings:
                    all_findings.append({"type": "jsluice", "data": jf, "file": file})

    # ppmap
    pp_result = await run_ppmap(url)
    if pp_result:
        all_findings.append({"type": "ppmap", "evidence": pp_result})

    # Store results in js-intelligence
    js_intel_list = get_storage_create("web-apps::js-intelligence", parent_id=app["id"])
    if js_intel_list:
        js_intel = js_intel_list[0]
        js_intel.add_many([{
            "url": url,
            "hash": content_hash,
            "findings": json.dumps(all_findings),
            "unpacked_path": unpacked_path,
        }], source="js_pipeline")

    # 3. AI Delegation (Only if not third party)
    if not is_third_party(url, content):
        await delegate_to_ai_js_analysis(app, url, [], all_findings)

async def delegate_to_ai_js_analysis(app, url, file_paths, tool_findings):
    # Prepares payload and delegates to AI via ACP.
    pass
"""
