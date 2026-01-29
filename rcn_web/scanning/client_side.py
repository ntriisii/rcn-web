import typing
import asyncio
import re
import random
import string
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from rcn_core.data_access import get_unprocessed_entries
from rcn_web.core.utils import web_match_storage
from rcn_core.storage.bases import add_annotation as global_add_annotation
from pentest_utils.web import HeadlessBrowser
from rcn_core.decorators import rcn_event


@rcn_event()
async def scan_client_side_reflected_content(event, scheduled_md):
    """
    Scans for Reflected XSS by fuzzing query parameters found in the referenced entry's path.
    Triggered by notes with key 'xss'.
    """
    scanner_name = event["name"]

    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        if not unscanned:
            return

        async with HeadlessBrowser() as browser:
            for item in unscanned.values():
                note_entry = item["entry"]
                referenced_entry = item.get("reference")
                storage = item["storage"]
                parent = item["parent"]

                if note_entry.get("key") != "potential-xss":
                    continue
                if not referenced_entry:
                    continue

                path = referenced_entry.get("path")
                if not path:
                    continue

                # Construct URL
                site = getattr(parent, "site", "")
                scheme = getattr(parent, "scheme", "https")
                base_url = getattr(parent, "url", f"{scheme}://{site}")
                target_url = base_url.rstrip("/") + "/" + path.lstrip("/")

                parsed = urlparse(target_url)
                query_params = parse_qs(parsed.query)

                if not query_params:
                    continue

                # Iterate over all parameters in the query string
                for param in query_params:
                    probe = "".join(
                        random.choices(string.ascii_letters + string.digits, k=8)
                    )

                    # Create modified query with probe
                    mod_query = query_params.copy()
                    mod_query[param] = [probe]

                    new_query_string = urlencode(mod_query, doseq=True)
                    fuzzed_url = urlunparse(parsed._replace(query=new_query_string))

                    try:
                        resp = await browser.get(fuzzed_url, timeout=10)

                        if probe in resp.text:
                            # Found reflection
                            ref_storage = item.get("reference_storage")
                            if ref_storage:
                                global_add_annotation(
                                    entry_id=referenced_entry["id"],
                                    storage_name=ref_storage.storage_name,
                                    key="reflection-detected",
                                    value=f"Q:{param}",
                                    parent_id=parent['id']
                                )

                    except Exception:
                        pass
