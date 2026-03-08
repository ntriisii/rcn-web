import os
import sys
import time
import random
import string
import pathlib
import asyncio
import aiofiles as aiof

from collections import defaultdict
from urllib.parse import urlparse, unquote_plus
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.utils import get_app_by_site

# Global state for batching
JS_COLLECTED_FLOWS = []
JS_COL_MAX_TIME = 10
JS_COL_TIME = time.time()


async def extract_js_files(flow):
    global JS_COL_TIME, JS_COL_MAX_TIME, JS_COLLECTED_FLOWS

    # Check if it's a JS file
    resp_headers = flow["response-headers"]
    # Check content-type or extension if content-type is missing/generic
    is_js = "javascript" in resp_headers.get("content-type", "")
    if not is_js:
        path = urlparse(flow["url"]).path
        if path.endswith(".js"):
            is_js = True

    if is_js:
        JS_COLLECTED_FLOWS.append(
            {"url": flow["url"], "response": flow["response-body"]}
        )

    # Batching logic: return accumulated flows only after interval or if enough gathered
    # Here we stick to time-based as in original, but could add count threshold
    if time.time() - JS_COL_TIME >= JS_COL_MAX_TIME and JS_COLLECTED_FLOWS:
        JS_COL_TIME = time.time()
        tmp = JS_COLLECTED_FLOWS
        JS_COLLECTED_FLOWS = []
        return tmp

    return None


async def handle_collected_js_files(s, extractor, js_content):
    if not js_content:
        return

    # Group by site
    found_sites = defaultdict(list)
    for js_entry in js_content:
        site = urlparse(js_entry["url"]).netloc
        found_sites[site].append(js_entry)

    for site, site_entries in found_sites.items():
        temp_files = []
        try:
            # Write to temp files
            for entry in site_entries:
                # Generate unique temp filename
                rand_suffix = "".join(
                    random.choices(string.ascii_letters + string.digits, k=10)
                )
                fname = f"js_analysis_{rand_suffix}.js"
                temp_path = os.path.join("/tmp", fname)

                async with aiof.open(temp_path, "w") as f:
                    await f.write(entry["response"])

                temp_files.append(temp_path)

            if temp_files:
                await js_analysis_run_flow_on_files(s, temp_files, site)

        finally:
            # Cleanup temp files
            for p in temp_files:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception as e:
                    print(f"Error deleting temp file {p}: {e}")


async def js_analysis_run_flow_on_files(s, paths, app_name):
    import rcn_core.globals

    # Use global RCN_FLOWS directly or via storage method
    if hasattr(s, "get_rcn_flows"):
        flows = s.get_rcn_flows()
    else:
        flows = rcn_core.globals.RCN_FLOWS

    flow_cls = flows.get("js-analysis-with-jsluice")
    if not flow_cls:
        print("js-analysis-with-jsluice flow not found")
        return

    flow = flow_cls()
    # Pass space-separated paths as expected by the underlying tool wrapper
    collected_paths = " ".join(paths)
    flow.set_data([collected_paths])

    try:
        out = await flow.run()
    except Exception as e:
        print(f"Error running js analysis flow: {e}")
        return

    if not out:
        return

    app = get_app_by_site(s, app_name)
    if not app:
        app = get_app_by_site(s, app_name)
        if not app:
            return

    # Collect data by type
    links = []
    secrets = []
    for i in out:
        if "kind" in i.keys():
            secrets.append(i)
        else:
            links.append(i)

    if links:
        lst = get_storage_create("web-apps::js-links", parent_id=app["id"])
        # Add proper source and original keys if missing, though logic implies they exist
        lst.add_many(
            [
                {
                    "url": i.get("url"),
                    "source": i.get("source"),
                    "original": i.get("original"),
                }
                for i in links
            ],
            source="jsluice",
        )

    if secrets:
        sst = get_storage_create("web-apps::js-secrets", parent_id=app["id"])
        sst.add_many(
            [
                {
                    "source": i.get("source"),
                    "reason": i.get("reason"),
                    "match": i.get("match"),
                }
                for i in secrets
            ],
            source="jsluice",
        )
