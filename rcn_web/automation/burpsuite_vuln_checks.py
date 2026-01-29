import os
import re
import copy
import asyncio
import json
import aiohttp

from .utils import automation_get_storage_data, automation_get_storage_links

from rcn_core.log import rlog


SCANNING_DESC = dict()


def get_scanning_desc():
    global SCANNING_DESC

    if not SCANNING_DESC:
        desc_file = os.path.expanduser(
            "~/.config/rcn-server/burp-scanning-description.json"
        )
        with open(desc_file, "r") as f:
            SCANNING_DESC = json.load(f)

    return SCANNING_DESC


# TODO: names should be issues and use the detection methods
# to include specific methods
def burp_scan_get(severities=[], names=[], indecies=[]):
    if not severities and not names and not indecies:
        return get_scanning_desc()

    collected = []
    descs = get_scanning_desc()
    for i in descs:
        if (
            (not severities or i["severity"] in severities)
            and (not names or i["name"] in names)
            and (not indecies or i["index"] in indecies)
        ):
            collected.append(i)

    return collected


async def burp_api_available():
    async with aiohttp.ClientSession() as sess:
        try:
            resp = await sess.get("http://localhost:1337/")
            return resp.status == 200
        except aiohttp.ClientConnectionError:
            return False


# TODO: more customization
def burp_make_scanning_config(indices, scope=None, resouces_pool=None):
    template = dict()
    template_file = os.path.expanduser(
        "~/.config/rcn-server/burp_scanning_template_config.json"
    )
    with open(template_file, "r") as f:
        template = json.load(f)

    issues = template["scanner"]["issues_reported"]["selected_issues"]
    for iss in issues:
        if iss["type_index"] in indices:
            iss["enabled"] = True

    return json.dumps(template)


async def burp_scan_urls(urls, scanning_config):
    loc = None
    config = json.dumps(scanning_config, separators=(",", ":"))
    async with aiohttp.ClientSession() as sess:
        resp = await sess.post(
            url="http://localhost:1337/v0.1/scan",
            json={
                "urls": urls,
                "scan_configurations": [
                    {"config": scanning_config, "type": "CustomConfiguration"}
                ],
            },
        )

        # get the ID of the scan
        loc = resp.headers["location"]

    if not loc:
        rlog("there was an error running burp scanner", level="warn")

    # FIXME: timeout the loop
    time = len(urls) / 50
    while True:
        async with aiohttp.ClientSession() as sess:
            resp = await sess.get(
                url=f"http://localhost:1337/v0.1/scan/{loc}",
            )
            c = await resp.json()
            if c.get("scan_status") in ["succeeded", "failed"]:
                break

        await asyncio.sleep(time)


burp_scans = {
    "xss": [
        "Cross-site scripting (stored)",
        "Cross-site scripting (reflected)",
        "Cross-site scripting (DOM-based)",
        "Cross-site scripting (reflected DOM-based)",
        "Cross-site scripting (stored DOM-based)",
    ],
    "sqli": ["SQL injection", "SQL injection (second order)"],
    "command injection": ["OS command injection"],
}


async def burp_automation_run_scan(scans: "list[str]", data: list):

    global burp_scans

    scans_to_run = []
    for scan in scans:
        scans_to_run.extend(burp_scans[scan])

    # get the scans
    issues = burp_scan_get(names=scans_to_run)
    burp_scans_indicies = [i["index"] for i in issues]

    # make scan configuration
    config = burp_make_scanning_config(
        burp_scans_indicies,
    )
    links = automation_get_storage_links(data)
    if links:
        links = [re.sub("https://.*/", "http://localhost:8023/", i) for i in links]

    print(await burp_scan_urls(urls=links, scanning_config=config))


async def burp_scan_xss(data):
    print("operating on ", data)
    return await burp_automation_run_scan(scans=["xss"], data=data)
