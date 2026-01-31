
from rcn_core.log import rlog
from rcn_core.data_access import get_storage, get_unprocessed_entries
from rcn_web.core.utils import web_match_storage, get_app_by_site
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.scope import flow_in_scope
from collections import defaultdict
from urllib.parse import urlparse

from rcn_web.flows import *
from rcn_core.decorators import rcn_event


@rcn_event()
async def trufflehog_check_for_flow_secrets(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        flows = [i["entry"] for i in unscanned.values()]
        if not flows: return

        results = []
        for flow in flows:
            if not flow_in_scope(flow): continue

            try:
                res = await trufflehog_operate(flow)
                if res: results.extend(res)
                
            except Exception as e: rlog(f"Error in trufflehog_operate: {e}", level="error")

        if results: await trufflehog_store_data(get_storage(), event, {"data": results})


@rcn_event()
async def collect_in_scope_urls(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        flows = [i["entry"] for i in unscanned.values()]
        if not flows:
            return

        results = []
        for flow in flows:
            if not flow_in_scope(flow):
                continue

            try:
                res = await collect_url_content(flow)
                if res:
                    results.extend(res)
            except Exception as e:
                rlog(f"Error in collect_url_content: {e}", level="error")

        if results:
            await handle_collected_urls(get_storage(), event, results)


@rcn_event()
async def collect_js_files(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        flows = [i["entry"] for i in unscanned.values()]
        if not flows: return

        results = []
        for flow in flows:
            if not flow_in_scope(flow): continue

            try:
                res = await extract_js_files(flow)
                if res: results.extend(res)
                
            except Exception as e: rlog(f"Error in extract_js_files: {e}", level="error")

        if results: await handle_collected_js_files(get_storage(), event, results)


@rcn_event()
async def store_app_flows(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        flows = [i["entry"] for i in unscanned.values()]
        if not flows:
            return

        found_sites_data = defaultdict(list)
        for flow in flows:
            if not flow_in_scope(flow):
                continue

            url = flow.get("url")
            if not url:
                continue

            site = urlparse(url).netloc
            found_sites_data[site].append(flow)

        st = get_storage()
        for site, site_flows in found_sites_data.items():
            app = get_app_by_site(st, site)
            if not app: continue

            items_to_store = []
            for flow in site_flows:
                flow_id = flow.get("timestamp")
                p = urlparse(flow["url"])
                path = p.path + ("?" + p.query if p.query else "")

                items_to_store.append({"flow-id": flow_id, "path": path})

            if items_to_store:
                flow_storage = get_storage_create("web-apps::app-flows", parent_id=app['id'])
                flow_storage.add_many(items_to_store, source="proxy")


@rcn_event()
async def store_js_flows(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        flows = [i["entry"] for i in unscanned.values()]
        if not flows: return

        found_sites_data = defaultdict(list)
        for flow in flows:
            if not flow_in_scope(flow): continue

            # Check if JS
            headers_list = flow.get("response-headers", [])
            content_type = ""
            if isinstance(headers_list, dict):
                content_type = headers_list.get("content-type", "") or headers_list.get("Content-Type", "")
            else:
                for h in headers_list:
                    if h[0].lower() == "content-type":
                        content_type = h[1]
                        break
            
            path = urlparse(flow.get("url", "")).path
            is_js = "javascript" in content_type.lower()
            if not is_js and path.endswith(".js"):
                is_js = True
            
            if is_js:
                site = urlparse(flow["url"]).netloc
                found_sites_data[site].append(flow)

        st = get_storage()
        for site, site_flows in found_sites_data.items():
            app = get_app_by_site(st, site)
            if not app: continue

            items_to_store = []
            for flow in site_flows:
                flow_id = flow.get("timestamp") or flow.get("id")
                p = urlparse(flow["url"])
                path = p.path + ("?" + p.query if p.query else "")
                items_to_store.append({"flow-id": flow_id, "path": path})

            if items_to_store:
                flow_storage = get_storage_create("web-apps::js-flows", parent_id=app['id'])
                flow_storage.add_many(items_to_store, source="proxy")

            
