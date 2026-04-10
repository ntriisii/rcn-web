import time
import datetime
import asyncio
import validators
import aiohttp
import ipaddress

from bs4 import BeautifulSoup as soup

from rcn_web.core.utils import get_storage, get_root_storage
from rcn_core.utils import time_str_to_secs
from rcn_core.log import rlog


def handle_shodan_io_request(response):
    t1 = time.perf_counter()
    response = soup(response, "html.parser")
    gen_info = response.find("div", {"class": "card card-yellow card-padding"})
    running_services = (
        response.findAll("div", {"class": "card card-padding banner"}) or []
    )
    vuln_info = response.find("div", {"class": "card card-red card-padding"}) or []

    # parse general info about IP addr
    general_info = {}
    last_key = None

    if gen_info:
        found_info = gen_info.text.split("\n\n")[1:]
        found_info = [i for i in found_info if i][1:]
        for i in found_info:

            i = i.strip()

            # only a key without a value, values may follow in upcoming lines
            if i.find("\n") == -1:
                if not last_key:
                    general_info[i] = None
                    last_key = i

                elif general_info[last_key] == None:
                    general_info[last_key] = i.strip()
                elif isinstance(general_info[last_key], list):
                    general_info[last_key] = [*general_info[last_key], i.strip()]
                elif isinstance(general_info[last_key], str):
                    general_info[last_key] = [general_info[last_key], i.strip()]

            # skip searching in the beginning of the string
            elif i.strip().find("\n", 1) != -1:
                i = i.strip()
                key, val = i.split("\n", 1)
                general_info[key.strip()] = val.strip()
                last_key = key

            # either in the first or the last of the string put it directly in the last key
            elif i.find("\n"):
                val = general_info.get(last_key)
                if isinstance(val, list):
                    general_info[last_key].append(i.strip())
                elif isinstance(val, str):
                    general_info[last_key] = [val, i.strip()]
                elif val == None:
                    general_info[last_key] = i.strip()

    vulnerability_info = []
    if vuln_info:
        # parse vuln info
        for info in vuln_info.findAll("tr") or []:
            d = info.findAll("td") or []
            if len(d) == 2:
                key = d[0].text.strip()
                value = d[1].text.strip()
                vulnerability_info.append(key)

    # parse running services
    services_mapping = []
    if running_services:
        for service in running_services:
            try:
                service_pre_banner = (
                    service.previous_sibling.previous_sibling.text.split("\n")
                )
                service_pre_banner = [i for i in service_pre_banner if i != ""]

                generated_at = service_pre_banner[2].split("|")[1].strip()
                service_port = service_pre_banner[0].replace("/", "").strip()
                service_proto = service_pre_banner[1].replace("/", "").strip()
                banner_data = service.find("h1", {"class": "banner-title"})
                banner_data = banner_data.findAll("a") if banner_data else []
                service_name = banner_data[0].text if banner_data else ""
                service_version = banner_data[1].text if len(banner_data) > 1 else ""
                content = service.text.split("\n")
                content = content if content[0] != "" else content[1:]
                content = "".join(content if not service_name else content[1:])
                d = {
                    "name": service_name,
                    "version": service_version,
                    "port": service_port,
                    "protocol": service_proto,
                    "generated-at": generated_at,
                    "content": content,
                }

                services_mapping.append(d)

            # TODO: should be tested against mutliple IPs first then
            # check what causes errors and fix it
            except Exception:
                continue

    all_data = {
        "vulns": vulnerability_info,
        "services": services_mapping,
        "general-info": general_info,
    }

    return all_data


async def get_shodan_ip_data(ip: str):

    if not ip:
        return
    out = dict()

    try:
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(verify_ssl=False)
        ) as session:
            url = "https://www.shodan.io/host/" + ip
            headers = {
                "host": "www.shodan.io",
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-encoding": "gzip, deflate, br, zstd",
                "accept-language": "en-US,en;q=0.9,ar;q=0.8",
                "cache-control": "max-age=0",
                "cookie": 'polito="c6ac05e4e48154f79acee8288e0a171c68a1e67064ebcce876860627f14aa4db!";',
                "priority": "u=0, i",
                "referer": "https://www.shodan.io/dashboard?language=en",
                "sec-ch-ua": 'Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": 'Linux"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "same-origin",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            }

            resp = await session.get(url, allow_redirects=False, headers=headers)

            shdn_data = handle_shodan_io_request(await resp.text())
            shdn_data["ip"] = ip
            out = shdn_data

    except:
        return {"vulns": [], "services": [], "general-info": {}, "ip": ip}

    return out


def add_found_ips(entries):
    to_add = []
    for i in entries:
        if validators.ipv4(i):
            to_add.extend([str(i) for i in ipaddress.IPv4Network(i)])
        else:
            to_add.extend([str(i) for i in ipaddress.IPv6Network(i)])
    return [{"ip": ip} for ip in to_add]


def handle_shodan_io_content(content):
    st = get_root_storage()
    shodan_storage = st.get_storage_create("shodan-scrapped-ips")
    found_ips = st.get_storage_create("found-ips")
    subdomains = st.get_storage_create("domains")

    shodan_storage.add_many(content, source="shodan")
    found_ips.add_many([i["ip"] for i in content], source="shodan")

    if content:
        content = content[0]
    else:
        return

    if content.get("general-info"):
        subdomains.add_many(
            [
                i
                for i in (
                    (
                        content["general-info"].get("domains", [])
                        + content["general-info"].get("hostnames", [])
                    )
                )
            ],
            source="shodan",
        )


async def scan_shodan_for_ips(event, scheduled_md, matched_storages=[]):
    s = get_root_storage()
    debug = event.get("debug")
    ip_storage = s.get_storage_create("found-ips")
    repeat_checks_time = event.get("repeat-every", "1 day")
    repeat_every = time_str_to_secs(repeat_checks_time)
    last_index = scheduled_md.get("shodan-last-scanned-index") or 0
    last_repeat = scheduled_md.get("shodan-last-repeat")
    shodan_storage = s.get_storage_create("shodan-scrapped-ips").get()
    ctime = datetime.datetime.now().timestamp()
    to_check = ip_storage.get()[last_index:]

    if debug:
        rlog("last_index", last_index, "length of data: ", len(ip_storage.get()))
        if last_repeat:
            rlog(
                "last_repeat", datetime.datetime.fromtimestamp(last_repeat).isoformat()
            )

    if last_index >= len(ip_storage.get()) and (
        not last_repeat or ctime - last_repeat >= repeat_every
    ):

        rlog("repeating the shodan process after", repeat_checks_time)
        scheduled_md["shodan-last-repeat"] = ctime
        last_index = 0

    to_check = ip_storage.get()[last_index:]
    shodan_ips = {i["ip"]: i for i in shodan_storage}
    per_time = event.get("ips-per-time", 15)
    ips = []

    # collect the per_time ips
    count = 0
    while len(ips) < per_time and count < len(to_check):
        cip = to_check[count]["ip"]
        p = shodan_ips.get(cip)
        if not p or ctime - p["timestamp"] >= repeat_every:
            ips.append(cip)

        count += 1

    if debug:
        rlog("running shodan on ", len(ips))
        rlog("counted", count, "IPs")

    tasks = []
    for ip in ips:
        tasks.append(asyncio.create_task(get_shodan_ip_data(ip)))

    gathered = await asyncio.gather(*tasks)
    handle_shodan_io_content(gathered)

    scheduled_md["shodan-last-scanned-index"] = last_index + (
        count if count else len(to_check)
    )
