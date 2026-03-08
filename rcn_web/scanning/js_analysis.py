import os
import asyncio
import aiohttp
import aiofiles as aiof
import json
import time
from urllib.parse import urlparse

from rcn_core.data_access import (
    get_storage,
    get_unprocessed_entries,
    get_storage_create,
)
from rcn_web.core.utils import (
    web_match_storage,
    get_app_by_site,
    is_in_scope,
)
from rcn_core.decorators import rcn_event
from rcn_core.storage.bases import add_annotation as global_add_annotation
from rcn_core.log import rlog

from rcn_web.core.js_utils import (
    get_js_hash,
    deobfuscate_js,
    run_semgrep,
    run_jsluice,
    run_ppmap,
    is_third_party,
    start_jxscout,
    fetch_via_jxscout,
)


@rcn_event()
async def js_intelligence_monitor(event, scheduled_md):
    """
    Monitors web-apps::js-links for new JS files,
    tracks their hashes, and triggers analysis on change.
    """
    scanner_name = event["name"]

    # Ensure jxscout is running for the current target if configured
    target_obj = event.get("target")
    if target_obj:
        # MultiTargetStorage might have targets dict, or it might be a single TargetStorage
        project_name = getattr(target_obj, "name", "default_target")
        await start_jxscout(project_name)

    async with get_unprocessed_entries(
        scanner_name, event, match_storage_fn=web_match_storage
    ) as unscanned:
        if not unscanned:
            return

        # Group by app to optimize
        app_js_map = {}
        for item in unscanned.values():
            app = item["parent"]
            if app["id"] not in app_js_map:
                app_js_map[app["id"]] = {"app": app, "links": []}
            app_js_map[app["id"]]["links"].append(item["entry"])

        async with aiohttp.ClientSession() as session:
            for app_id, data in app_js_map.items():
                app = data["app"]
                js_inventory = get_storage_create(
                    "web-apps::js-inventory", parent_id=app_id
                )

                for js_link in data["links"]:
                    url = js_link.get("url")
                    if not url or not url.endswith(".js"):
                        continue

                    # Only analyze if the domain is in scope
                    domain = urlparse(url).netloc
                    if not is_in_scope(domain):
                        continue

                    try:
                        async with session.get(url, timeout=30) as resp:
                            if resp.status != 200:
                                continue
                            content = await resp.text()

                        current_hash = await get_js_hash(content)

                        # Check inventory
                        existing = js_inventory.get_filtered(f"url = '{url}'")
                        is_changed = True
                        if existing:
                            if existing[0].get("hash") == current_hash:
                                is_changed = False

                        if is_changed:
                            # Update inventory
                            inventory_entry = {
                                "url": url,
                                "hash": current_hash,
                                "last_seen": time.time(),
                                "is_third_party": is_third_party(url, content),
                                "status": "pending_analysis",
                            }
                            js_inventory.add_many(
                                [inventory_entry], source="js_monitor"
                            )

                            # Trigger Analysis Pipeline for this file
                            # (We'll do this in a separate event or here directly)

                            # Optional: reconstruct via jxscout
                            await fetch_via_jxscout(url)

                            # For now, let's process it
                            await process_js_file(app, url, content, current_hash)

                    except Exception as e:
                        rlog(f"Error monitoring JS {url}: {e}", level="error")


async def process_js_file(app, url, content, content_hash):
    """
    Core pipeline for a single JS file.
    """
    rlog(f"Processing JS file: {url}")

    # 1. Deobfuscate
    unpacked_path, success = await deobfuscate_js(content, url)

    # 2. Tools Analysis
    all_findings = []

    # Semgrep
    semgrep_findings = await run_semgrep(unpacked_path)
    for f in semgrep_findings:
        all_findings.append(
            {
                "type": "semgrep",
                "rule": f.get("check_id"),
                "location": f.get("path"),
                "line": f.get("start", {}).get("line"),
                "evidence": f.get("extra", {}).get("lines"),
                "severity": f.get("extra", {}).get("severity"),
            }
        )

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
    js_intel = get_storage_create("web-apps::js-intelligence", parent_id=app["id"])
    js_intel.add_many(
        [
            {
                "url": url,
                "hash": content_hash,
                "findings": json.dumps(all_findings),
                "unpacked_path": unpacked_path,
            }
        ],
        source="js_pipeline",
    )

    # 3. AI Delegation (Only if not third party)
    if not is_third_party(url, content):
        await delegate_to_ai_js_analysis(app, url, unpacked_path, all_findings)


async def delegate_to_ai_js_analysis(app, url, source_path, tool_findings):
    """
    Prepares payload and delegates to AI via ACP.
    """
    # Sample code from the recovered source
    # We might want to read a few interesting files
    code_samples = ""
    count = 0
    for root, dirs, files in os.walk(source_path):
        for file in files:
            if file.endswith(".js") and count < 5:
                fpath = os.path.join(root, file)
                async with aiof.open(fpath, "r") as f:
                    code = await f.read()
                    code_samples += (
                        f"\nFILE: {file}\n```javascript\n{code[:2000]}\n```\n"
                    )
                count += 1

    ai_prompt = f"""
I need you to perform a deep security analysis of the following JavaScript source code recovered from {url}.
Target Application: {app["site"]}

Tool Findings:
{json.dumps(tool_findings, indent=2)}

Source Code Samples (Recovered):
{code_samples}

**Your Task**: 
1. Analyze the code for logic flaws, authentication bypasses, or sensitive data leaks.
2. YOU MUST ACT AS A FUNCTION. Return Python code that I can execute to record your findings.
3. Upon finishing your analysis and testing, you must record your findings by calling the provided functions.
4. Use `add_annotation(category='js-analysis', key='finding', value='...')` for vulnerabilities.
5. Use `add_annotation(category='js-analysis', key='notify', value='...')` for interesting endpoints or attack surface.
6. If you see a clear exploitation path, call `delegate_to_acp(agent_name='exploit_agent', instructions='...')`.

Return ONLY the Python code inside a code block.
"""

    # Create an ACP annotation for the agent to pick up
    xml_value = f"""
<instructions>{ai_prompt}</instructions>
<storage>web-apps::js-intelligence</storage>
<app_name>{app["site"]}</app_name>
"""
    global_add_annotation(
        entry_id=url,
        storage_name="targets::annotations",
        key="js-analyst",
        value=xml_value,
        parent_id=app["id"],
        category="acp-agent-do",
    )
