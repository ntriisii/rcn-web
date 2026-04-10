from rcn_core.log import rlog
from rcn_core.data_access import get_storage, get_unprocessed_entries
from rcn_web.core.utils import web_match_storage, get_app_by_site, get_root_storage
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.scope import flow_in_scope
from collections import defaultdict
from urllib.parse import urlparse

from rcn_web.flows import *
from rcn_core.decorators import rcn_event
from rcn_web.core.utils import get_app_by_site


@rcn_event()
async def trufflehog_check_for_flow_secrets(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(
        scanner_name, event, match_storage_fn=web_match_storage
    ) as unscanned:
        flows = [i["entry"] for i in unscanned.values()]
        if not flows:
            return

        results = []
        for flow in flows:
            if not flow_in_scope(flow):
                continue

            try:
                res = await trufflehog_operate(flow)
                if res:
                    results.extend(res)

            except Exception as e:
                rlog(f"Error in trufflehog_operate: {e}", level="error")

        if results:
            await trufflehog_store_data(get_root_storage(), event, {"data": results})


@rcn_event()
async def collect_in_scope_urls(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(
        scanner_name, event, match_storage_fn=web_match_storage
    ) as unscanned:
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
            await handle_collected_urls(get_root_storage(), event, results)


@rcn_event()
async def collect_js_files(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(
        scanner_name, event, match_storage_fn=web_match_storage
    ) as unscanned:
        flows = [i["entry"] for i in unscanned.values()]
        if not flows:
            return

        results = []
        for flow in flows:
            if not flow_in_scope(flow):
                continue

            try:
                res = await extract_js_files(flow)
                if res:
                    results.extend(res)

            except Exception as e:
                rlog(f"Error in extract_js_files: {e}", level="error")

        if results:
            await handle_collected_js_files(get_root_storage(), event, results)
