
import os
import re
import jq
import sys
import json
import typing
import random
import asyncio
import fnmatch
import validators
import subprocess
import aiofiles as aiof
import aiohttp

from collections import defaultdict
from urllib.parse import urlparse
from itertools import groupby
from contextlib import asynccontextmanager

import rcn_core.globals as cglobals

from rcn_core.data_access import get_storage, rr_server_hosts_stats, rr_server_remote_hosts_count
from rcn_core.storage.bases import get_storage_create
from rcn_core.log import rlog
from rcn_core.data_access import get_storage
from rcn_web.config import *
from rcn_web.core.utils import web_match_storage, get_app_by_site
from rcn_core.utils import parse_json

# from rcn_web.storage.url import handle_crawling_collected_urls
from rcn_core.data_access import get_unprocessed_entries
from rcn_core.decorators import rcn_event



def parse_ffuf_content(content):
    content_sorted = sorted(content, key=lambda entry: entry["status"])
    content_sorted = groupby(content_sorted, key=lambda entry: entry["status"])
    content_sorted = {i[0]: list(i[1]) for i in content_sorted}

    to_return = []
    for i in content_sorted:
        if len(content_sorted[i]) >= 400:
            to_return.extend(random.choices(content_sorted[i], k=20))
        else:
            to_return.extend(content_sorted[i])
    return to_return


def get_nuclei_host_and_path(nuclei_host):
    nuclei_host = nuclei_host.strip(".")
    if validators.domain(nuclei_host):
        return nuclei_host.strip("."), "/"
    elif validators.url(nuclei_host):
        p = urlparse(nuclei_host)
        return (p.netloc, p.path + ("?" + p.query if p.query else ""))
    elif validators.ipv4(nuclei_host):
        return nuclei_host, "/"
    elif validators.ipv6(nuclei_host):
        return nuclei_host, "/"

    # check for something like domain:port
    else:
        return nuclei_host, "/"


async def handle_nuclei_scanning_entries(content, source="nuclei-scanning"):
    # should not do this but there must be a problem with httpx for example
    if not content:
        return
    tmpl_dir = os.path.expanduser("~/AllForOne/Templates/")
    found_apps = defaultdict(list)
    for entry in content:
        site, path = get_nuclei_host_and_path(entry["host"])
        entry = {
            "template-id": entry["template-id"],
            "template-path": entry["template-path"].replace(
                "/tmp/Templates/", tmpl_dir
            ),
            "name": entry["info"].get("name", ""),
            "severity": entry["info"].get("severity", "unknwon"),
            "host": entry["host"],
        }

        found_apps[site].append(entry)

    s = get_storage()
    for site in found_apps:
        app = get_app_by_site(s, site)
        data = found_apps[site]

        if not app:
            app = get_app_by_site(s, site)
        if not app:
            continue

        # store in the app scanning data only if the target path is /
        nc_storage = get_storage_create("web-apps::nuclei-scanning", parent_id=app['id'])
        site_vuln_ids = [i["template-id"] for i in nc_storage.get()]
        for entry in data:
            host, path = get_nuclei_host_and_path(entry["host"])
            print("adding nuclei data related to ", host, path)
            if not any(entry["template-id"] == i for i in site_vuln_ids):
                nc_storage.add_many([entry], source=source)
                site_vuln_ids.append(entry["template-id"])


@rcn_event()
async def crawl_application(event, scheduled_md):
    kt_additional_args = event.get("katana-args", "")
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        apps = [i["entry"] for i in unscanned.values()]

        if apps:
            apps_links = [app["url"] for app in apps]
            async with aiof.open("/tmp/to_crawl_apps.txt", "w") as f:
                await f.write("\n".join(apps_links))

            # TODO: don't use proxy and create a flow that can translate to a piped operation
            # to handle application data and what you want from it.
            from rcn_core.time_event import start_scheduled_process
            await start_scheduled_process(
                f"rr katana -u /tmp/to_crawl_apps.txt {kt_additional_args} ---chunks-per-host 1 -ob -jc -jsl -silent -aff -fx -j -proxy http://localhost:8081 -ef woff,css,png,svg,jpg,woff2,jpeg,gif,svg -kf all -xhr ---debug | jq -c 'del(.response.body) | del(.response.raw)' ",
                timeout=event.get("timeout"),
                debug=event.get("debug"),
                name=event.get("name"),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            
            # print(results)
            # print(results.split('\n')[:10])
            # TODO: make sure all data from katana are included in the proxy
            # NOTE: skip data from katana as the proxy handles those
            # await handle_crawling_collected_urls(parse_json(results.split('\n')))


async def run_nuclei_scan(targets_file_path, templates_path, nuclei_args, timeout=None, debug=False, name=""):
    cmd = f"rr nuclei -l {targets_file_path}:l1 -t {templates_path} {nuclei_args} -duc "
    
    from rcn_core.time_event import start_scheduled_process
    results = await start_scheduled_process(
        cmd,
        timeout=timeout,
        debug=debug,
        name=name,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=True,
    )
    
    return results


@rcn_event()
async def nuclei_scan_apps(event, scheduled_md, matched_storage=[]):
    fn_name = event["name"]
    timeout = event.get("timeout")
    debug = event.get("debug")
    scanner_name = fn_name
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        apps = [i["entry"] for i in unscanned.values()]
        if apps:
            async with aiof.open("/tmp/nuclei_c_apps.txt", "w") as f:
                await f.write("\n".join([i["site"] for i in apps]))

            results = await run_nuclei_scan(
                "/tmp/nuclei_c_apps.txt",
                "/tmp/Templates/",
                nuclei_args,
                timeout=timeout,
                debug=debug,
                name=fn_name
            )

            # handle data
            await handle_nuclei_scanning_entries(
                [json.loads(i) for i in results.split("\n")]
            )


async def run_ffuf_scan(target_url, wordlists, additional_args="", timeout=None, debug=False, name=""):
    all_wordlists = ",".join(wordlists)
    cmd = f"rr ffuf -u {target_url}FUZZ -json -noninteractive -w {all_wordlists}:l1 ---min-chunk-length 500 {additional_args} "
    # print("running", cmd)
    from rcn_core.time_event import start_scheduled_process
    results = await start_scheduled_process(
        cmd,
        timeout=timeout,
        debug=debug,
        name=name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )
    
    if not results:
        return []

    to_add = [
        {
            "path": urlparse(i["url"]).path,
            "status": i["status"],
            "words": i["words"],
            "lines": i["lines"],
            "length": i["length"],
            "response-hash": i["lines"] + i["length"] + i["words"],
        }
        for i in parse_json(results.split("\n"))
    ]

    return parse_ffuf_content(to_add)


@rcn_event()
async def application_fuzzing(event, scheduled_md, matched_storage=[]):

    fn_name = event["name"]
    remote_wordlists = event.get("remote-wordlist", [])
    local_wordlists = event.get("local-wordlists", [])
    ffuf_args = event.get("ffuf-args", "")
    timeout = event.get("timeout")
    debug = event.get("debug")
    scanner_name = fn_name
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        apps = [i["entry"] for i in unscanned.values()]
        if apps:
            for app in apps:
                url = app["url"][: app["url"].find("/", 10)]
                to_add = await run_ffuf_scan(
                    url, 
                    remote_wordlists + local_wordlists, 
                    ffuf_args, 
                    timeout=timeout, 
                    debug=debug,
                    name=fn_name
                )

                if not to_add:
                    continue

                # add the fuzzing results
                fz_storage = get_storage_create("web-apps::fuzzing-data", parent_id=app['id'])

                # Add all results to storage first
                fz_storage.add_many(to_add, source="ffuf-fuzzing")

                # Check for valid 200 status requests by identifying outliers
                status_200_entries = [
                    entry for entry in to_add if entry["status"] == 200
                ]
                if status_200_entries:
                    # Group 200 entries by common response characteristics (lines, words, size)
                    # to identify potentially fake 200s that return generic error pages
                    from collections import Counter

                    # Create a counter of common response signatures (lines, words)
                    response_signature_counts = Counter(
                        (entry["lines"], entry["words"]) for entry in status_200_entries
                    )

                    # Identify signatures that appear many times (likely generic responses)
                    common_signatures = {
                        sig
                        for sig, count in response_signature_counts.items()
                        if count
                        > len(status_200_entries) * 0.5  # More than 50% of responses
                    }

                    # Valid 200s are those that don't have common signatures (outliers)
                    valid_200_entries = [
                        entry
                        for entry in status_200_entries
                        if (entry["lines"], entry["words"]) not in common_signatures
                    ]

                    # For valid 200s (outliers), make additional requests through proxy to further validate
                    if valid_200_entries:
                        async with aiohttp.ClientSession() as session:
                            for entry in valid_200_entries:
                                full_url = url + entry["path"]
                                try:
                                    # Request through proxy to further validate the 200 response
                                    async with session.get(
                                        full_url, proxy="http://localhost:8081"
                                    ) as proxy_response:
                                        # Read response to further validate if 200 is genuine
                                        response_text = await proxy_response.text()
                                        response_status = proxy_response.status
                                        response_size = len(response_text)

                                        # Additional validation can be done here if needed

                                except aiohttp.ClientError:
                                    # Handle connection errors, timeouts, etc.
                                    continue
