import re
import json
import time
import hashlib

from bs4 import BeautifulSoup as soup
from urllib.parse import urlparse, urljoin, parse_qs
from collections import defaultdict

from pentest_utils.web.request import detect_content_type, parse_by_content_type
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.utils import get_app_by_site

# from rcn_web.core.utils import *
# from rcn_web.storage.url import form_to_request


def form_to_request(form, base_url, headers):
    """Returns `form` as a request URL"""

    method = (form.get("method", "GET")).upper()
    url = urljoin(form.get("action", ""), base_url)
    ctype = form.get("enctype", "unknown")
    params = form.get("parameters", [])
    data = ""

    # make data based on the method
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
        "flow-id": None,
    }


COLLECTED_REQUEST_INFO = list()
LAST_SEND_TIME = time.time()
SEND_TIME = 10


def extract_flow_forms(parsed, flow):
    resp_headers = flow["response-headers"]
    to_return = []
    content_type = resp_headers.get("content-type", "")

    if not "html" in content_type:
        return []

    forms = parsed.findAll(
        "form",
    )

    if not forms:
        return []
    for form in forms:
        # Extract basic attributes
        data = {
            "method": form.get("method", "get").upper(),
            "action": form.get("action", ""),
            "parameters": [],
        }

        # Extract enctype from attributes or form content
        data["enctype"] = form.get("enctype", "")
        if not data["enctype"] and (data["method"] == "POST" or "file" in form.text):
            data["enctype"] = "multipart/form-data"

        # Extract parameter names from different input types
        for input_field in form.find_all("input"):
            name = input_field.get("name")
            if name:
                data["parameters"].append(name)

        for select_field in form.find_all("select"):
            name = select_field.get("name")
            if name:
                data["parameters"].append(name)

        for textarea in form.find_all("textarea"):
            name = textarea.get("name")
            if name:
                data["parameters"].append(name)

        to_return.append(data)

    return to_return


async def collect_url_content(flow):
    url = flow["url"]
    path = flow["path"]
    resp_ctype = flow["response-headers"].get("content-type", None)
    resp_ctype = (
        resp_ctype or flow["response-headers"].get("Content-Type", ["unkown"])
    )[0]

    # print("collecting", url, "at", flow['timestamp'])

    req_ctype = flow["request-headers"].get("content-type", ["unknown"])[0]
    status = int(flow["status"])
    method = flow["method"]
    method = (
        "GET" if method == "HEAD" else method
    )  # sometimes we use curl to fetch wayback URLs
    resp_length = len(flow["response-body"])
    req_body = flow["request-body"]

    print(flow["response-body"][:100])
    title = re.findall(re.compile("<title>.*?</title>"), flow["response-body"])
    if title: title = title[0]
    else: title = ""
    
    return [
        {
            "url": url,
            "path": path,
            "status": status,
            "method": method,
            "response-ctype": resp_ctype,
            "request-ctype": req_ctype,
            "response-length": resp_length,
            "data": req_body,
            "title": title,
            "flow-id": str(flow["timestamp"]),
        }
    ]


async def handle_collected_urls(st, extractor, content):
    data = content
    found_sites_data = defaultdict(list)

    for u in data:
        site = urlparse(u["url"]).netloc
        status = int(u["status"])
        u["status"] = status
        u["response-length"] = int(u["response-length"])

        # filter requests
        if status in [404, 400]:
            continue

        found_sites_data[site].append(u)

    for site in found_sites_data:
        # get the application related to it
        app_st = get_app_by_site(st, site)

        if not app_st:
            continue

        d = found_sites_data[site]
        url_storage_list = get_storage_create(
            "web-apps::app-links", parent_id=app_st["id"]
        )
        app_flow_storage_list = get_storage_create(
            "web-apps::app-flows", parent_id=app_st["id"]
        )
        js_flow_storage_list = get_storage_create(
            "web-apps::js-flows", parent_id=app_st["id"]
        )

        if (
            not url_storage_list
            or not app_flow_storage_list
            or not js_flow_storage_list
        ):
            continue

        url_storage = url_storage_list[0]
        app_flow_storage = app_flow_storage_list[0]
        js_flow_storage = js_flow_storage_list[0]

        js_flow_storage = get_storage_create(
            "web-apps::js-flows", parent_id=app_st["id"]
        )

        app_flows_to_add = []
        js_flows_to_add = []

        for entry in d:
            url = entry["url"]
            p = urlparse(url)
            path = p.path + ("?" + p.query if p.query else "")
            flow_id = entry["flow-id"]

            app_flows_to_add.append({"flow-id": flow_id, "path": path})

            # Check if JS
            is_js = False
            ctype = entry.get("response-ctype", "").lower()
            if "javascript" in ctype or p.path.endswith(".js"):
                is_js = True

            if is_js:
                js_entry = entry.copy()
                js_entry["path"] = path
                js_flows_to_add.append(js_entry)

            # save some space by removing the URL and rebuild it when required
            entry["path"] = path
            if "url" in entry:
                del entry["url"]

        url_storage.add_many(d, source="proxy")

        if app_flows_to_add:
            app_flow_storage.add_many(app_flows_to_add, source="proxy")

        if js_flows_to_add:
            # Deduplicate js flows if they are from links (proxy entries usually have flow-id)
            existing_js_flows = {
                i.get("url") for i in js_flow_storage.get() if i.get("url")
            }
            unique_js_flows = []
            seen_urls = set()
            for l in js_flows_to_add:
                u = l.get("url")
                if u not in existing_js_flows and u not in seen_urls:
                    unique_js_flows.append(l)
                    seen_urls.add(u)
                elif not u:  # if no url, just add it (standard flow)
                    unique_js_flows.append(l)

            if unique_js_flows:
                js_flow_storage.add_many(unique_js_flows, source="proxy")


async def collect_request_info(flow):
    """
    Collects request headers, response headers, parameter and body keys.
    """
    global COLLECTED_REQUEST_INFO, LAST_SEND_TIME

    # 1. Extract header keys
    request_header_keys = [
        h.lower() for h in dict(flow.get("request-headers", {})).keys()
    ]

    # 2. Extract parameter keys from URL query
    url = flow.get("url", "")
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    parameter_keys = list(query_params.keys())

    # 3. Extract keys from request body
    request_body = flow.get("request-body", b"")
    # Make a dictionary from headers to easily get content-type
    request_headers = dict(flow.get("request-headers", {}))

    body_keys = []

    if request_body:
        ctype = detect_content_type(request_body)
        parsed = parse_by_content_type(request_body, ctype)
        body_keys = list(parsed.keys())

    all_parameter_keys = sorted(list(set(parameter_keys + body_keys)))

    # Don't store if we have nothing interesting
    if not all_parameter_keys and not request_header_keys:
        return None

    COLLECTED_REQUEST_INFO.append(
        {
            "url": url,
            "request_header_keys": request_header_keys,
            "parameter_keys": all_parameter_keys,
        }
    )

    t = time.time()
    if t - LAST_SEND_TIME >= SEND_TIME:
        LAST_SEND_TIME = t
        content = {"data": COLLECTED_REQUEST_INFO}
        COLLECTED_REQUEST_INFO = list()
        return content

    else:
        return None


async def handle_collected_request_info(st, extractor, content):
    """
    Handles collected request info and stores it.
    """
    data = content.get("data", [])
    if not data:
        return

    found_sites_data = defaultdict(list)
    for item in data:
        site = urlparse(item["url"]).netloc
        found_sites_data[site].append(item)

    for site in found_sites_data:
        app_st = get_app_by_site(st, site)
        if not app_st:
            app_st = get_app_by_site(st, site)
        if not app_st:
            continue

        req_storage_list = get_storage_create(
            "web-apps::requests-collected-info", parent_id=app_st["id"]
        )
        if not req_storage_list:
            continue
        req_storage = req_storage_list[0]

        items_to_add = found_sites_data[site]
        collected = []
        for entry in items_to_add:
            param_keys = entry.get("parameter_keys", [])
            rheader_keys = entry.get("request_header_keys", [])
            resheader_keys = entry.get("response_header_keys", [])

            for i in param_keys:
                collected.append({"value": i, "type": "parameter"})
            for i in rheader_keys:
                collected.append({"value": i, "type": "request-header"})

        # Fix: use the correct storage variable
        req_storage.add_many(items_to_add, source="proxy")
