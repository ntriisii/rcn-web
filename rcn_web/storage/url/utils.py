import re
import asyncio
import sys
import pathlib
import os
import glob
import datetime
import json
import time
import requests
import hashlib
import aiofiles as aiof
import aiohttp
import base64

from collections import defaultdict
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from mitmproxy.http import Headers

import rcn_core.globals

from rcn_web.core.utils import get_storage, get_root_storage, get_app_by_site, get_app_by_id, add_apps
from rcn_core.storage.bases import get_storage_create
from rcn_core.log import rlog
from pentest_utils.utils import id_hash


static_ext = (
    "css", "png", "jpg", "jpeg", "svg", "ico", "webp", "scss", "tif", "tiff",
    "ttf", "otf", "woff", "woff2", "gif", "pdf", "bmp", "eot", "mp3", "mp4", "avi",
)
interesting_ext = ("js", "xml", "json")


def http_raw_request_to_flow(base_url: str, raw_http_content: str):
    """transforms Org raw request to HTTP flow"""
    
    flow = dict()
    head_content = raw_http_content.split("\n\n", 1)
    body_content = ""
    
    if len(head_content) >= 2:
        body_content = head_content[1]

    head_content = head_content[0].strip()
    body_content = body_content.strip()
    hlines = head_content.splitlines()
    
    metadata = {}
    for i in hlines[1:]:
        if not i.strip().startswith("#"):
            break
        md_key = re.search(":[a-zA-Z0-9\-_]+?:", i)
        if not md_key:
            break
        md_key = i[md_key.start() + 1 : md_key.end() - 1]
        md_value = i.split(":", 2)[2].strip()
        metadata[md_key] = md_value
    
    body_content = "\r\n".join(
        [i for i in body_content.splitlines() if not i.strip().startswith("#")]
    )
    
    body_content = body_content.strip("\r\n")
    mline = hlines[0]
    hlines = [i for i in hlines if not i.strip().startswith("#")]

    try:
        if len(mline.split()) < 3:
            raise InvalidHTTPContent("invalid method line specification")

        method = mline.split(" ", 1)[0].strip()
        http_version = mline.split(" ")[-1].strip()
        path = mline.strip().removeprefix(method).removesuffix(http_version).strip()

    except IndexError:
        raise InvalidHTTPContent("invalid method line specification")

    flow["metadata"] = metadata
    flow["method"] = method
    flow["url"] = base_url + path
    flow["http-version"] = http_version
    flow["request-body"] = body_content

    headers = hlines[1:]
    hdr_dict = dict()

    for head in headers:
        try:
            head = head.split(": ", 1)
            key = head[0].strip()
            value = head[1].strip()
        except IndexError:
            raise InvalidHTTPContent("invalid headers specification")
        hdr_dict[key] = value

    flow["request-headers"] = hdr_dict
    flow["request-body"] = base64.b64encode(
        flow["request-body"].encode("utf-8")
    ).decode("ascii")
    return flow


class InvalidHTTPContent(Exception):
    pass


def form_to_request(form, base_url, headers):
    """Returns form as a request URL"""
    
    method = (form.get("method", "GET")).upper()
    url = urljoin(form.get("action", ""), base_url)
    ctype = form.get("enctype", "unknown")
    params = form.get("parameters", [])
    data = ""
    
    if method == "GET":
        url += "?" + "&".join(i + "=FUZZ" for i in params)
    else:
        data = "&".join(i + "=FUZZ" for i in params)
    
    p = urlparse(url)
    path = p.path + ("" if not p.query else "?" + p.query)
    raw_headers = "\n".join(str(i[0]) + ": " + str(i[1]) for i in headers.items())
    raw_request = (
        f"{method} {path} HTTP/1.1"
        + "\n"
        + raw_headers
        + ("\n" + "content-type: " + ctype if ctype != "unknown" else "")
        + "\n\n"
        + data
    )
    
    return {
        "url": url,
        "method": method,
        "request-ctype": ctype,
        "response-ctype": "unkown",
        "data": data,
        "raw-request": raw_request,
        "status": 0,
        "title": "",
        "response-length": 0,
    }


def app_links_id_fn(entry):
    def uniq_data(data, content_type):
        keys = []
        if "json" in content_type:
            try:
                keys = json.loads(data).keys()
            except json.JSONDecodeError:
                pass
        elif "form-urlencoded" in content_type:
            keys = parse_qs(data).keys()
        else:
            keys = [data]
        return "::".join(sorted(list(keys)))

    p = urlparse(entry["path"])
    path = p.path.strip("?")
    query = "::".join(sorted(list(parse_qs(p.query).keys())))
    status = entry["status"]
    method = entry["method"]
    data = "::".join(sorted(list(parse_qs(entry["data"]).keys())))
    content_type = entry["request-ctype"]
    if status == 404:
        return 1
    if str(status)[0] in ["4", "3"]:
        status = 1
    return id_hash(query + path + method + uniq_data(data, content_type))


async def handle_collected_urls(extractor, content):
    data = content["data"]
    st = get_root_storage()
    found_sites_data = defaultdict(list)
    for u in data:
        site = urlparse(u["url"]).netloc
        status = u["status"]
        if status in [404, 400]:
            continue
        found_sites_data[site].append(u)

    for site in found_sites_data:
        app = get_app_by_site(st, site)
        
        if not app:
             add_apps(st, [{'url': f'https://{site}', 'title': 'Discovered by URL Collection'}])
             app = get_app_by_site(st, site)
        
        if not app:
            continue

        d = found_sites_data[site]
        url_storage = get_storage_create("web-apps::app-links", parent_id=app['id'])

        for entry in d:
            p = urlparse(entry["url"])
            entry["path"] = p.path + ("?" + p.query if p.query else "")
            del entry["url"]

        url_storage.add_many(d, source="proxy")


def raw_request_extract_headers_and_body(raw_req):
    headers, data = raw_req.split("\r\n\r\n", 1)
    headers = headers.splitlines()[1:]
    headers = {i.split(": ")[0]: i.split(": ")[1] for i in headers}
    return headers, data.strip()


async def handle_crawling_collected_urls(content):
    def entry_to_standard(e):
        req = e["request"]
        resp = e["response"]
        raw_request = req.get("raw", "")
        c = raw_request.split("\n\n", 1)
        if len(c) == 2:
            raw_request = c[0] + "\nx-rcn-server-no-store: true\n\n" + c[1]
        else:
            raw_request = c[0] + "\nx-rcn-server-no-store: true\n\n" + ""

        return {
            "url": req["endpoint"],
            "method": req["method"] if req["method"] != "HEAD" else "GET",
            "status": resp.get("status_code", 0),
            "response-ctype": resp["headers"].get("content_type", "unknown"),
            "response-length": resp["headers"].get("content_length", 0),
            "request-ctype": "unknown",
            "data": "",
            "title": "",
            "raw-request": raw_request,
        }

    data = []
    for entry in content:
        headers, body = raw_request_extract_headers_and_body(
            entry["request"].get("raw", "")
        )
        headers["x-rcn-server-no-store"] = "true"

        forms = entry["response"].get("forms", [])
        url = entry["request"].get("endpoint", "")
        data.append(entry_to_standard(entry))

        if forms:
            found_forms = [form_to_request(i, url, headers) for i in forms]
            data.extend(found_forms)

    await handle_collected_urls(
        extractor={},
        content={"data": data},
    )


async def add_gau_entries(all_entries):
    for i in range(0, len(all_entries), 4000):
        entries = all_entries[i : i + 4000]
        found_sites = defaultdict(list)
        for link in entries:
            p = urlparse(link)
            found_sites[p.netloc].append([None, None, link])

        st = get_root_storage()

        for site in found_sites:
            app = get_app_by_site(st, site)
            if not app:
                 add_apps(st, [{'url': f'https://{site}', 'title': 'Discovered by GAU'}])
                 app = get_app_by_site(st, site)
            
            if not app:
                continue

            wayback_storage = get_storage_create("web-apps::wayback-urls", parent_id=app['id'])
            wayback_storage.storage_md_set("wayback-fetched-all", True)
            wayback_storage.add_many(found_sites[site], source="waybackurls")


def get_links_fn(links: list):
    s = get_root_storage()
    new_obj = list()
    for link_obj in links:
        n = dict(link_obj)
        new_obj.append(n)
    return new_obj


async def request_gau_urls(event, scheduled_md, matched_storages=[]):
    async def request_url(url, ses):
        try:
            ses.head(
                url,
                proxy="http://localhost:8081",
                headers={
                    "user-agent": "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36"
                },
            )
        except aiohttp.ClientError as e:
            rlog("there was a problem requesting", url, "having error", e)

    gau_urls_path = pathlib.Path(os.path.join(sys.argv[1], ".gau_urls/"))
    if not gau_urls_path.exists():
        return

    files = glob.glob(gau_urls_path.as_posix() + "/*")
    rlog("requesting gau entries on files", len(files))
    max_request_per_time = event.get("max-requests-per-time", 2000)
    concurrent_requests = event.get("concurrent-requests", 5)

    files_counter = 0
    urls = []
    while len(urls) < max_request_per_time and files_counter < len(files):
        async with aiof.open(files[files_counter], "r") as f:
            content = (await f.read()).split("\n")
            req = content[: max_request_per_time - len(urls)]
            rest = content[max_request_per_time - len(urls) :]
            urls.extend(req)

        if rest:
            async with aiof.open(files[files_counter], "w") as f:
                await f.write("\n".join(rest))
            break
        else:
            files_counter += 1
    
    rlog("requesting gau entries on URLs", len(urls))
    
    ses = aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False))
    
    for u in urls:
        tasks = []
        if len(tasks) < concurrent_requests:
            tasks.append(asyncio.create_task(request_url(u, ses)))
        else:
            await asyncio.gather(*tasks)
            tasks = []

    to_delete_files = files[:files_counter]
    for f in to_delete_files:
        os.remove(f)
