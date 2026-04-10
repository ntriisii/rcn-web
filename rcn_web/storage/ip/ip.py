import datetime
import validators
import asyncio
import functools
import json
import asyncio
import validators
import ipaddress
import aiohttp

from ipwhois import IPWhois
from shodan import Shodan
from censys.search import SearchClient

from .utils import *

from rcn_web.core.utils import *
from rcn_core.utils import time_str_to_secs
from rcn_core.storage.bases import get_storage_create


SHODAN_IO_PENDING_IPS = []
CENSYS_SEARCH_IPS = []
UNPROCESSED_ASNS = []
"""used to collect IPs to request on cesnys search when it reaches a
specific number of IPs (etc 100) as not to waste API quota. """


from rcn_core.decorators import rcn_event

@rcn_event()
async def handle_unprocessed_ips(event):

    global CENSYS_SEARCH_IPS

    ip_entries = get_storage_create("found-ips")
    if not ip_entries:
        return

    new_ips = ip_entries.new_data
    data_id = list(new_ips.keys())[0]
    new_ips = list(new_ips.values())[0]
    new_ips = [i["ip"] for i in new_ips]
    if new_ips:
        CENSYS_SEARCH_IPS.extend(new_ips)
        CENSYS_SEARCH_IPS = list(set(CENSYS_SEARCH_IPS))

        flow = RCN_FLOWS["ips-flow"]()
        flow.set_data(new_ips)

        await flow.run()
        ip_entries.ack_data_processed(data_id)


@rcn_event()
async def handle_unprocessed_asns(event):
    global UNPROCESSED_ASNS

    asn_entries = get_storage_create("found-asns")
    if not asn_entries:
        return

    new_asns = asn_entries.new_data
    data_id = list(new_asns.keys())[0]
    new_asns = list(new_asns.values())[0]
    new_asns = [i["asn"] for i in new_asns]
    if new_asns:
        UNPROCESSED_ASNS.extend(new_asns)
        UNPROCESSED_ASNS = list(set(UNPROCESSED_ASNS))

        flow = RCN_FLOWS["asns-flow"]()
        flow.set_data(new_asns)

        await flow.run()
        asn_entries.ack_data_processed(data_id)


async def get_to_scan_ips(data):
    if len(data) > 1000:
        event_loop = asyncio.get_event_loop()
        ip_fn_packed = functools.partial(get_ips_related_to_target, data=data)
        return await event_loop.run_in_executor(None, ip_fn_packed)

    return data


def get_ips_related_to_target(data):
    # TODO: include the target CIDRs
    print("getting whois info for IPs")
    org_name_markers = ["hilton"]

    to_return = []
    matching_ranges = []
    not_matching_ranges = []
    for ip in data:
        if any(ipaddress.IPv4Address(ip) in i for i in matching_ranges):
            to_return.append(ip)
            continue

        elif any(ipaddress.IPv4Address(ip) in i for i in not_matching_ranges):
            continue

        try:
            whois_data = IPWhois(ip).lookup_rdap()
        except Exception as e:
            continue

        asn_desc = whois_data.get("asn_description") or ""
        emails = json.dumps(
            [
                (i.get("contact") or dict()).get("email") or ""
                for i in whois_data["objects"].values()
            ]
        )
        network_desc = json.dumps(whois_data.get("network") or dict())
        network_name = json.dumps(
            (whois_data.get("network") or dict()).get("name") or ""
        )
        objects_names = list((whois_data.get("objects") or dict()).keys())
        all_data = []

        all_data.append(asn_desc)
        all_data.append(network_desc)
        all_data.append(network_name)
        all_data.append(emails)
        all_data.extend(objects_names)

        # check which contains the organization markers from content
        cidr = whois_data.get("asn_cidr")
        if any(
            any(marker.lower() in entry.lower() for marker in org_name_markers)
            for entry in all_data
        ):

            if cidr and validators.ipv4(cidr):
                matching_ranges.append(ipaddress.IPv4Network(cidr))

            to_return.append(ip)

        else:
            if cidr and validators.ipv4(cidr):
                not_matching_ranges.append(ipaddress.IPv4Network(cidr))

    return to_return


async def shodan_internetdb_port_scan(data):
    found_data = []
    for ip in data:
        if ipaddress.IPv4Address(ip).is_private:
            continue
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(verify_ssl=False)
            ) as session:
                async with session.get(f"https://internetdb.shodan.io/{ip}") as resp:
                    content = await resp.json()
                    if "No information" not in (content.get("detail") or ""):
                        content["ip"] = ip
                        found_data.append(content)
        except:
            rlog(f"cannot reach URL internetdb.shodan.io/{ip}", level="warn")

    return found_data


def shodan_scan_ips(data):
    # arrange the IP data in ranges of 70
    # TODO change the 70
    prev = 0
    shodan_query_strings = []
    for curr in range(0, len(data) + 70, 70):
        ip_range = data[prev:curr]
        query_string = "ip:" + ",".join(ip_range)
        shodan_query_strings.append(query_string)
        prev = curr

    shodan_api = Shodan("iR4PKgBXzFISWqtTN2RZHW5Xq6jo6WPT")
    # check for the count for all those queries if collectively are more than
    # 5000 then skip
    c_total = 0
    to_search = []
    for query in shodan_query_strings:
        c_total += shodan_api.count(query)["total"]
        if c_total >= 5000:
            break
        to_search.append(query)

    # search for all the queries
    toreturn = []
    for query in to_search:
        cout = shodan_api.search_cursor(query)
        toreturn.append(cout)

    return toreturn


async def get_censys_data(data, per_query):
    censys_query_strings = []
    for curr in range(0, len(data) + per_query, per_query):
        ip_range = data[curr : curr + per_query]
        if not ip_range:
            continue

        query_string = "ip:" + " OR ip:".join(ip_range)
        censys_query_strings.append(query_string)

    censys_data = []
    results = []

    client = SearchClient()
    try:
        for query in censys_query_strings:
            results = client.v2.hosts.search(query)
            for i in results:
                censys_data.extend(i)
            await asyncio.sleep(3)
    except:
        print(censys_query_strings[-1])

    censys_storage = get_storage_create("censys-ips")
    rlog(f"collected {len(censys_data)} entries from censys...")
    collected_data = {}
    for i in censys_data:
        if i.get("ip"):
            collected_data[i["ip"]] = i
        else:
            rlog("cannot find IP in ", i, level="warn")

    all_data = []
    # check for missed IPs from censys
    for i in data:
        if not collected_data.get(i):
            rlog("cannot find IP in ", i, "in censys", level="warn")
            all_data.append({"ip": i, "services": []})
        else:
            all_data.append(collected_data[i])

    censys_storage.add_many(all_data, source="censys")


async def censys_scan_ips_scheduled(event, scheduled_md):

    global CENSYS_SEARCH_IPS

    from rcn_web.core.utils import get_target_storage
    censys_ips = get_storage_create("censys-ips")
    censys_ips.clear()
    CENSYS_SEARCH_IPS.extend([i["ip"] for i in get_target_storage()["found-ips"].get()])
    CENSYS_SEARCH_IPS = list(set(CENSYS_SEARCH_IPS))

    for i in range(len(CENSYS_SEARCH_IPS)):
        if validators.ipv6(CENSYS_SEARCH_IPS[i]):
            CENSYS_SEARCH_IPS[i] = f'"{CENSYS_SEARCH_IPS[i]}"'

    per_query = event.get("censys-ips-per-query", 100)
    if len(CENSYS_SEARCH_IPS) >= per_query:
        rlog("collecting censys data")
        rlog(f"working on {len(CENSYS_SEARCH_IPS)}")

        data = CENSYS_SEARCH_IPS
        CENSYS_SEARCH_IPS = []

        await get_censys_data(data, per_query)
        print("trying to run censys data on ", len(data))


async def censys_scan_ips(event):

    global CENSYS_SEARCH_IPS

    censys_ips = get_storage_create("censys-ips")

    # filter found IPs and normalize IPv6
    censys_ips = [i.get("ip", "") for i in censys_ips.get()]
    CENSYS_SEARCH_IPS = [i for i in CENSYS_SEARCH_IPS if i not in censys_ips]

    for i in range(len(CENSYS_SEARCH_IPS)):
        if validators.ipv6(CENSYS_SEARCH_IPS[i]):
            CENSYS_SEARCH_IPS[i] = f'"{CENSYS_SEARCH_IPS[i]}"'

    per_query = event.get("censys-ips-per-query", 100)
    if len(CENSYS_SEARCH_IPS) >= per_query:
        rlog("collecting censys data")
        rlog(f"working on {len(CENSYS_SEARCH_IPS)}")

        data = CENSYS_SEARCH_IPS
        CENSYS_SEARCH_IPS = []

        await get_censys_data(data, per_query)
        print("trying to run censys data on ", len(data))
