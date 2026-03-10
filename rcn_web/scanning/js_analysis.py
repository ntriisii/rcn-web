from rcn_web.storage.utils import get_uniq_apps
import os
import asyncio
import aiohttp
import time
from urllib.parse import urlparse

from rcn_core.data_access import (
    get_storage,
    get_unprocessed_entries,
    get_storage_create,
)
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
                rlog(f"Monitoring JS hashes for {app.get('site')}")

                links_tasks = [
                    handle_monitor_js_hash(session, semaphore, app, js_link)
                    for js_link in data["links"]
                ]
                results = await asyncio.gather(*links_tasks)

                inventory_entries = [r for r in results if r is not None]
                if inventory_entries:
                    js_inventory = get_storage_create(
                        "web-apps::js-inventory", parent_id=app_id
                    )
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
            js_inventory = get_storage_create(
                "web-apps::js-inventory", parent_id=app["id"]
            )

            # Check inventory
            existing = js_inventory.get_filtered(f"url = '{url}'")
            is_changed = True
            if existing:
                if existing[0].get("hash") == current_hash:
                    is_changed = False

            if is_changed:
                rlog(f"JS Hash changed for {url}")
                return {
                    "url": url,
                    "hash": current_hash,
                    "last_seen": time.time(),
                    "is_third_party": is_third_party(url, content),
                    "status": "monitored",
                }

        except Exception as e:
            rlog(f"Error monitoring hash for {url}: {e}", level="debug")

    return None


async def process_js_file(app, url, content, content_hash, project_name="default_target"):
    """
    Legacy pipeline - currently disabled.
    """
    pass


async def delegate_to_ai_js_analysis(app, url, file_paths, tool_findings):
    """
    Legacy AI delegation - currently disabled.
    """
    pass


            if app["id"] not in app_js_map:
                app_js_map[app["id"]] = {
                    "app": app,
                    "links": [],
                    "target_name": target_name,
                }
            app_js_map[app["id"]]["links"].append(item["entry"])

        # Limit concurrency to avoid overwhelming the target or proxy
        semaphore = asyncio.Semaphore(5)

        async with aiohttp.ClientSession() as session:
            for app_id, data in app_js_map.items():
                app = data["app"]
                project_name = data["target_name"]
                rlog(
                    f"Monitoring JS for app {app.get('site')} in project {project_name}"
                )

                # Ensure jxscout is running for this target
                # Include the app site in the scope to ensure jxscout handles it
                scope = f"*{app.get('site')}*"
                await start_jxscout(project_name, scope=scope)

                # # Batch Nuclei Scan for all links in this batch for this app
                # app_urls = [l["url"] for l in data["links"] if l.get("url")]
                # rlog(f"Running batch Nuclei scan for {len(app_urls)} URLs in {app.get('site')}")
                # batch_findings = await run_nuclei_js(app_urls)
                #
                # # Store findings in vuln storage
                # if batch_findings:
                #     from .utils import handle_nuclei_scanning_entries
                #     await handle_nuclei_scanning_entries(batch_findings, source="js_pipeline")
                #
                # # Group findings by URL for individual processing
                # url_nuclei_map = {}
                # for nf in batch_findings:
                #     found_url = nf.get("matched-at") or nf.get("url")
                #     if found_url not in url_nuclei_map:
                #         url_nuclei_map[found_url] = []
                #     url_nuclei_map[found_url].append(nf)

                links_tasks = [
                    handle_monitor_js_link(
                        session,
                        semaphore,
                        app,
                        js_link,
                        project_name,
                        # nuclei_findings=url_nuclei_map.get(js_link.get("url"), []),
                    )
                    for js_link in data["links"]
                ]

                # Process all links for this app
                results = await asyncio.gather(*links_tasks)

                # Batch update inventory for this app
                inventory_entries = [r for r in results if r is not None]
                if inventory_entries:
                    js_inventory = get_storage_create(
                        "web-apps::js-inventory", parent_id=app_id
                    )
                    js_inventory.add_many(inventory_entries, source="js_monitor")


async def handle_monitor_js_link(
    session, semaphore, app, js_link, project_name, nuclei_findings=None
):
    """
    Handles the lifecycle of a single JS link within the monitor.
    Returns the inventory entry if analysis was triggered, else None.
    """

    if nuclei_findings is None:
        nuclei_findings = []

    url = js_link.get("url")
    if not url:
        return None

    # Debugging: Log the source of this link
    source = js_link.get("source", "unknown")
    rlog(f"Evaluating JS link: {url} (source: {source}, app: {app.get('site')})")

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
                    if content:
                        rlog(f"Retrieved content for {url} from flow {flow_id}")

            if not content:
                # Fallback to direct fetch if not found in proxy or flow-id missing
                try:
                    async with session.get(url, timeout=20) as direct_resp:
                        if direct_resp.status == 200:
                            content = await direct_resp.text()
                            rlog(
                                f"Direct fetch successful for {url} ({len(content)} bytes)"
                            )
                except Exception as de:
                    rlog(f"Direct fetch failed for {url}: {de}", level="warn")

            if not content:
                rlog(
                    f"Could not retrieve content for {url} via any method",
                    level="error",
                )
                return None

            current_hash = await get_js_hash(content)
            js_inventory = get_storage_create(
                "web-apps::js-inventory", parent_id=app["id"]
            )

            # Check inventory
            existing = js_inventory.get_filtered(f"url = '{url}'")
            is_changed = True
            if existing:
                if existing[0].get("hash") == current_hash:
                    is_changed = False

            if is_changed:
                # Prepare inventory entry
                inventory_entry = {
                    "url": url,
                    "hash": current_hash,
                    "last_seen": time.time(),
                    "is_third_party": is_third_party(url, content),
                    "status": "pending_analysis",
                }

                # Trigger Analysis Pipeline
                await process_js_file(
                    app,
                    url,
                    content,
                    current_hash,
                    project_name,  # nuclei_findings
                )
                return inventory_entry

        except Exception as e:
            rlog(f"Error monitoring JS {url}: {e}", level="error")

    return None


async def process_js_file(
    app, url, content, content_hash, project_name="default_target", nuclei_findings=None
):
    """
    Core pipeline for a single JS file.
    """
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

    # also check if jxscout has reconstructed files for this domain
    jx_path = get_jxscout_path(project_name)
    domain = urlparse(url).netloc
    asset_path = os.path.join(jx_path, "assets", domain)
    rlog(f"Checking for jxscout assets at {asset_path}")
    if os.path.exists(asset_path):
        jx_assets = []
        for root, _, files in os.walk(asset_path):
            for f in files:
                jx_assets.append(os.path.relpath(os.path.join(root, f), asset_path))

        rlog(f"Found {len(jx_assets)} jxscout assets for {domain}: {jx_assets[:10]}...")

        if jx_assets:
            # Sample one asset content
            try:
                sample_asset = os.path.join(asset_path, jx_assets[0])
                async with aiof.open(sample_asset, "r") as f:
                    asset_content = await f.read()
                rlog(f"jxscout asset sample ({jx_assets[0]}): {asset_content[:200]}...")
            except:
                pass

        # Scan jxscout recovered sources too
        jx_semgrep = await run_semgrep(asset_path)
        for f in jx_semgrep:
            all_findings.append(
                {
                    "type": "semgrep-jxscout",
                    "rule": f.get("check_id"),
                    "location": f.get("path"),
                    "line": f.get("start", {}).get("line"),
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

    # # Nuclei Findings (passed from batch scan)
    # for nf in nuclei_findings:
    #     all_findings.append(
    #         {
    #             "type": "nuclei",
    #             "template": nf.get("template-id"),
    #             "info": nf.get("info", {}).get("name"),
    #             "matcher": nf.get("matcher-name"),
    #             "extracted": nf.get("extracted-results"),
    #         }
    #     )

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
        # Read some context from unpacked files
        context_files = []
        for root, dirs, files in os.walk(unpacked_path):
            for file in files:
                if file.endswith(".js") and len(context_files) < 10:
                    context_files.append(os.path.join(root, file))

        # Also check jxscout files if any
        if os.path.exists(asset_path):
            for root, dirs, files in os.walk(asset_path):
                for file in files:
                    if (file.endswith(".js") or file.endswith(".ts")) and len(
                        context_files
                    ) < 20:
                        context_files.append(os.path.join(root, file))

        await delegate_to_ai_js_analysis(app, url, context_files, all_findings)


async def delegate_to_ai_js_analysis(app, url, file_paths, tool_findings):
    """
    Prepares payload and delegates to AI via ACP.
    """
    code_samples = ""
    for fpath in file_paths:
        try:
            async with aiof.open(fpath, "r") as f:
                code = await f.read()
                filename = os.path.basename(fpath)
                code_samples += (
                    f"\nFILE: {filename}\n```javascript\n{code[:1500]}\n```\n"
                )
        except:
            continue

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
