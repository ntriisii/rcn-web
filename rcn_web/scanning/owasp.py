
import typing
import subprocess
import aiofiles as aiof

from operator import itemgetter
from itertools import groupby
from contextlib import asynccontextmanager
from functools import partial

from rcn_web.core.utils import storage
from rcn_web.core.utils import parse_json, web_match_storage
from pentest_utils.ai import ai_ask
from .utils import get_unprocessed_entries



async def scan_xss(event, scheduled_md):
    """
    Perform XSS scanning on applications.
    
    Args:
        event: Event configuration
        scheduled_md: Scheduled metadata
        matched_storages: List of matched storages (applications)
    """
    
    to_scan_urls = []
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        # collect the entries into a file
        for link in unscanned:
            # FIXME: only process GET for now
            if link["link"]["method"] == "GET":
                link_id = link["link"]["id"]
                app = link["app"]
                app_url = app.scheme + "://" + app.site
                # use the fragment trick to easily map links when done processing
                to_scan_urls.append(app_url + link["entry"]["path"] + "#" + link_id)
        
        async with aiof.open("/tmp/xss_to_scan_links.txt", "w") as f:
            await f.write("\n".join(to_scan_urls))
        
        args = ""
        # for links in (unscanned_entries_get, unscanned_entries_post):
        command = f"rr xss-scan /tmp/xss_to_scan_links.txt:l1 " + args
        from rcn_core.time_event import start_scheduled_process
        results = await start_scheduled_process(
            command,
            timeout=event.get("timeout"),
            debug=event.get("debug"),
            name=event.get("name"),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        
        if results:
            results_json = parse_json(i for i in results.split("\n"))
            for entry in results_json:
                u = entry["url"]
                uid = int(u.split("#", 1)[1].strip())
                url_entry = unscanned[uid]["entry"]
                
                # create the notes object
                if url_entry.get("notes") is None:
                    url_entry["notes"] = dict()
                if url_entry["notes"].get("xss-scan") is None:
                    url_entry["notes"]["xss-scan"] = list()
                
                url_entry["notes"]["xss-scan"].append(entry)


@asynccontextmanager
async def collect_potential_vuln_urls(event, key):
    scanner_name = event["name"]
    from rcn_core.data_access import get_unprocessed_annotations
    async with get_unprocessed_annotations(key, scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        to_scan = []
        for item in unscanned.values():
            entry = item["entry"]
            
            if entry.get("key") == key:
                link = item.get("reference")
                if not link: continue
                
                app = item["parent"]
                url = f"{app.scheme}://{app.site}{link['path']}"
                
                # Use the fragment trick to store the link ID
                to_scan.append({"url": f"{url}#{link['id']}", "value": entry["value"]})
        
        yield to_scan


async def scan_potential_xss(event, scheduled_md):
    key = "potential-xss"
    async with collect_potential_vuln_urls(event, key) as to_scan:
        if to_scan:
            print("having those endpoints as xss scanning entries")
            print(to_scan)
            
            # file_path = f"/tmp/{note_key}_scan_urls.txt"
            # async with aiof.open(file_path, "w") as f:
            #     await f.write("\n".join(to_scan))
            
            # await start_scheduled_process(
            #     event,
            #     f"rr xss-scan {file_path}:l1",
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.DEVNULL,
            # )
            

async def scan_potential_csrf(event, scheduled_md):
    key = "potential-csrf"
    async with collect_potential_vuln_urls(event, key) as to_scan:
        if to_scan:
            print("having those endpoints as xss scanning entries")
            print(to_scan)

            # file_path = f"/tmp/{note_key}_scan_urls.txt"
            # async with aiof.open(file_path, "w") as f:
            #     await f.write("\n".join(to_scan))

            # await start_scheduled_process(
            #     event,
            #     f"rr {note_key} {file_path}:l1",
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.DEVNULL,
            # )


async def scan_potential_sqli(event, scheduled_md):
    key = "potential-sqli"
    async with collect_potential_vuln_urls(event, key) as to_scan:
        if to_scan:
            print("having those endpoints as xss scanning entries")
            print(to_scan)
            
            # file_path = f"/tmp/{note_key}_scan_urls.txt"
            # async with aiof.open(file_path, "w") as f:
            #     await f.write("\n".join(to_scan))

            # await start_scheduled_process(
            #     event,
            #     f"rr {note_key} {file_path}:l1",
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.DEVNULL,
            # )


async def scan_potential_rce(event, scheduled_md):
    key = "potential-rce"
    async with collect_potential_vuln_urls(event, key) as to_scan:
        if to_scan:
            print("having those endpoints as xss scanning entries")
            print(to_scan)

            # file_path = f"/tmp/{note_key}_scan_urls.txt"
            # async with aiof.open(file_path, "w") as f:
            #     await f.write("\n".join(to_scan))

            # await start_scheduled_process(
            #     event,
            #     f"rr {note_key} {file_path}:l1",
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.DEVNULL,
            # )


async def scan_potential_ssrf(event, scheduled_md):
    key = "potential-ssrf"
    async with collect_potential_vuln_urls(event, key) as to_scan:
        if to_scan:
            print("having those endpoints as xss scanning entries")
            print(to_scan)
            
            # file_path = f"/tmp/{note_key}_scan_urls.txt"
            # async with aiof.open(file_path, "w") as f:
            #     await f.write("\n".join(to_scan))

            # await start_scheduled_process(
            #     event,
            #     f"rr {note_key} {file_path}:l1",
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.DEVNULL,
            # )


async def scan_potential_file_upload(event, scheduled_md):
    key = "potential-file-upload"
    async with collect_potential_vuln_urls(event, key) as to_scan:
        if to_scan:
            print("having those endpoints as xss scanning entries")
            print(to_scan)

            # file_path = f"/tmp/{note_key}_scan_urls.txt"
            # async with aiof.open(file_path, "w") as f:
            #     await f.write("\n".join(to_scan))

            # await start_scheduled_process(
            #     event,
            #     f"rr {note_key} {file_path}:l1",
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.DEVNULL,
            # )


async def scan_potential_path_traversal(event, scheduled_md):
    key = "potential-path-traversal"
    async with collect_potential_vuln_urls(event, key) as to_scan:
        if to_scan:
            print("having those endpoints as xss scanning entries")
            print(to_scan)

            # file_path = f"/tmp/{note_key}_scan_urls.txt"
            # async with aiof.open(file_path, "w") as f:
            #     await f.write("\n".join(to_scan))
            
            # await start_scheduled_process(
            #     event,
            #     f"rr {note_key} {file_path}:l1",
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.DEVNULL,
            # )


async def scan_potential_blind_xss(event, scheduled_md):
    key = "potential-blind-xss"
    async with collect_potential_vuln_urls(event, key) as to_scan:
        if to_scan:
            print("having those endpoints as xss scanning entries")
            print(to_scan)

            # file_path = f"/tmp/{note_key}_scan_urls.txt"
            # async with aiof.open(file_path, "w") as f:
            #     await f.write("\n".join(to_scan))

            # await start_scheduled_process(
            #     event,
            #     f"rr {note_key} {file_path}:l1",
            #     stdout=subprocess.PIPE,
            #     stderr=subprocess.DEVNULL,
            # )
