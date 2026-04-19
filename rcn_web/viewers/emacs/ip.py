import re
import copy
import base64
import asyncio
import datetime
import sys

from pentest_utils.viewers.emacs.utils import (
    make_org_link,
    make_preview_tabulated_entries,
    basic_match_fn,
)
from .target import elisp_make_org_headline
from rcn_web.core.utils import get_storage, get_target_storage, get_app_by_site
from rcn_web.storage.ip import get_shodan_ip_data
from rcn_web.core.scope import get_inscope_domains
from rcn_web.storage.ip import shodan_internetdb_port_scan


def preview_ip_data(target):
    ip_storage = target.get_storage_create("shodan-internetdb-ips")
    shodan_content = target.get_storage_create("shodan-scrapped-ip-storage")


def view_ip_data(target, match_groups=None, create_windows=True, **kwargs):
    if not match_groups:
        match_groups = dict()

    ip_data = ips_all_sources_info()

    ip_entries, tabulated_format = make_ip_tabulated_entries(
        ip_data, match_groups, **kwargs
    )
    collected = dict()
    collected["window-config"] = {
        "window-1": {
            "buffer-name": "*ip-entries*",
            "mode": "tabulated-list-mode",
            "tabulated-format": tabulated_format,
            "entries": ip_entries,
            "storage-name": ".*ip.*",
            "is-target-storage": True,
            "navigate-fn": "rcn-view-ip",
            "refresh-fn": "rcn-view--ips-refresh",
            "view-store-name": "ips-data",
        },
        "window-2": {
            "buffer-name": "*current-ip-data*",
            "mode": "org-mode",
            "entries": {},
        },
        "orientation": "horizontal",
        "scale": 0.4,
        "min-width": 1000,
    }
    collected["view-store"] = {
        "ips-data": {
            "tabulated-data": {"get-ids-url": "http://localhost:8023/"},
            "default-directory": sys.argv[1],
        },
        "parent-storage": "targets",
    }

    if create_windows:
        return collected
    else:
        return collected["window-config"]["window-1"]["entries"]


def make_ip_tabulated_entries(ip_data, match_groups, **kwargs):
    attrs = (
        (
            "ip",
            20,
        ),
        ("ports", 20),
        ("vulns", 3),
        ("cpes", 20),
    )

    class _ListView:
        __slots__ = ("data", "length")

        def __init__(self, d):
            self.data = d
            self.length = len(d)

        def get_view_data(
            self,
            query_node=None,
            limit=100,
            after_id=None,
            before_id=None,
            sort_desc=True,
            sort_by=None,
        ):
            res = self.data
            if query_node is not None:
                res = [e for e in res if query_node.evaluate(e)]
            if after_id is not None:
                idx = next(
                    (i for i, e in enumerate(res) if str(e.get("id")) == str(after_id)),
                    -1,
                )
                if idx != -1:
                    res = res[idx + 1 :]
            elif before_id is not None:
                idx = next(
                    (
                        i
                        for i, e in enumerate(res)
                        if str(e.get("id")) == str(before_id)
                    ),
                    -1,
                )
                if idx != -1:
                    res = res[:idx]
            if sort_desc:
                res = res[::-1]
            return res[:limit]

    tbl_entries, tabl_format = make_preview_tabulated_entries(
        _ListView(ip_data), attrs, match_groups=match_groups, **kwargs
    )

    return tbl_entries, tabl_format


def extract_censys_relevant_data(censys_entry):
    c_ip = copy.deepcopy(censys_entry)
    c_ip["general-info"] = dict()
    if c_ip.get("location"):
        c_ip["location"] = c_ip["location"].get("country") or c_ip["location"].get(
            "country_code"
        )

    if c_ip.get("operating_system"):
        c_ip["operating_system"] = (
            " "
            + c_ip["operating_system"].get("vendor", "")
            + " "
            + c_ip["operating_system"].get("source", "")
            + " "
            + c_ip["operating_system"].get("part", "")
            + " "
            + c_ip["operating_system"].get("cpe", "")
        )

    if c_ip.get("autonomous_system"):
        c_ip["general-info"]["ASN-name"] = c_ip.get("autonomous_system", dict()).get(
            "name", ""
        )
        c_ip["general-info"]["bgp_prefix"] = c_ip.get("autonomous_system", dict()).get(
            "bgp_prefix", ""
        )

    return c_ip


def ips_all_sources_info():
    internetdb_st_list = get_target_storage().get_storage_create(
        "shodan-internetdb-ips"
    )
    internetdb_content = []
    for st in internetdb_st_list:
        internetdb_content.extend(st.get())

    shodan_st_list = get_target_storage().get_storage_create("shodan-scrapped-ips")
    shodan_content = []
    for st in shodan_st_list:
        shodan_content.extend(st.get())

    censys_st_list = get_target_storage().get_storage_create("censys-ips")
    censys_content = []
    for st in censys_st_list:
        censys_content.extend(st.get())
    found_data = {}

    # MAYBE: just expand it in new list
    ip_data = copy.deepcopy(internetdb_content)
    c_ips = [i.get("ip") for i in ip_data]
    ip_data += [
        {
            "ports": [j["port"] for j in i.get("services", [])],
            "cpes": [i.get("operating_system", dict()).get("cpe", "")],
            "ip": i.get("ip"),
            "vulns": [],
        }
        for i in censys_content
        if i.get("ip") not in c_ips
    ]

    c_ips = [i.get("ip") for i in ip_data]
    ip_data += [
        {
            "ports": [j["port"] for j in i.get("services", [])],
            "cpes": [],
            "ip": i.get("ip"),
            "vulns": [],
        }
        for i in shodan_content
        if i.get("ip") not in c_ips
    ]

    for ip_d in ip_data:
        ip = ip_d["ip"]
        s_ip = dict()

        # collect shodan data for IP
        if shodan_content:
            shodan_ip = [i for i in shodan_content if i["ip"] == ip]
            if s_ip:
                s_ip = copy.deepcopy(shodan_ip[0])

        if not s_ip:
            s_ip = {"general-info": {}, "services": [], "ip": ip_d["ip"]}
        # check out censys data
        c_ip = dict()
        if censys_content:
            entry = [i for i in censys_content if i["ip"] == ip]
            if entry:
                c_ip = copy.deepcopy(entry[0])

        s_ip.update(extract_censys_relevant_data(c_ip))

        if s_ip or c_ip:
            s_ip["general-info"]["operating_system"] = c_ip.get("operating_system", "")
            s_ip["general-info"]["location"] = c_ip.get("location", "")
            s_ip["general-info"]["censys-collect-date"] = c_ip.get(
                "last_updated_at", ""
            )
            if c_ip.get("autonomous_system"):
                s_ip["general-info"]["ASN-name"] = c_ip.get(
                    "autonomous_system", dict()
                ).get("name", "")
                s_ip["general-info"]["bgp_prefix"] = c_ip.get(
                    "autonomous_system", dict()
                ).get("bgp_prefix", "")

            if c_ip:
                lupdate = s_ip["general-info"]["censys-collect-date"]
                s_ip["services"].extend(
                    [
                        {
                            "port": i["port"],
                            "name": i["extended_service_name"],
                            "generated-at": lupdate,
                            "version": "",
                        }
                        for i in c_ip["services"]
                        if str(i["port"])
                        not in [j["port"] for j in s_ip.get("services", [])]
                    ]
                )

            s_ip.update(ip_d)
            s_ip["id"] = ip_d["ip"]

        found_data[ip_d["ip"]] = s_ip

    return found_data


def elisp_make_ip_view(ip):
    def domain_to_app_site(domain):
        st = get_target_storage()
        app = get_app_by_site(st, domain)

        # # add the application if in scope
        # if not app and get_inscope_domains([domain]):
        #   asyncio.create_task(st, domain))

        link = ""
        if app:
            link = make_org_link(
                f'elisp:(rcn-view--view-app-org-content "{app["site"]}")', app["site"]
            )
        else:
            link = make_org_link("https://" + domain + "/", domain)

        return link

    internetdb_st_list = get_target_storage().get_storage_create(
        "shodan-internetdb-ips"
    )
    shodan_st_list = get_target_storage().get_storage_create("shodan-scrapped-ips")
    censys_st_list = get_target_storage().get_storage_create("censys-ips")

    idb_ip = None
    if internetdb_st_list:
        internetdb_storage = internetdb_st_list[0]
        idb_content = internetdb_storage.get()
        idb_ip = [i for i in idb_content if i["ip"] == ip]

        if idb_ip:
            idb_ip = copy.deepcopy(idb_ip[0])
        else:
            idb_ip = None

    s_ip = None
    if shodan_st_list:
        shodan_content = shodan_st_list[0]
        s_content = shodan_content.get()
        s_ip = [i for i in s_content if i["ip"] == ip]

        if s_ip:
            # change the services to something more compact
            s_ip = copy.deepcopy(s_ip[0])

            # remove the services content as it takes too much space
            # and is not needed anyway
            for service in s_ip.get("services", []):
                if service.get("content"):
                    del service["content"]

            # hostnames and domains are transformed into links
            hostnames = s_ip["general-info"].get("Hostnames")
            if hostnames is not None:
                hostnames = hostnames if type(hostnames) is list else [hostnames]
                if hostnames:
                    s_ip["general-info"]["Hostnames"] = [
                        domain_to_app_site(i) for i in hostnames
                    ]

            domains = s_ip["general-info"].get("Domains")
            if domains is not None:
                domains = domains if type(domains) is list else [domains]
                if domains:
                    s_ip["general-info"]["Domains"] = [
                        domain_to_app_site(i) for i in domains
                    ]

        else:
            s_ip = None

    # check out censys data
    c_ip = None
    if censys_st_list:
        censys_content = censys_st_list[0]
        cn_d = censys_content.get()
        entry = [i for i in cn_d if i["ip"] == ip]
        if entry:
            c_ip = copy.deepcopy(entry[0])
            # c_ip['services'] = [str(i['port'] ).ljust(10)+\
            #                     i['extended_service_name']
            #                     for i in c_ip['services']
            #                     ]

            # adjust location
            if c_ip.get("location"):
                c_ip["location"] = c_ip["location"].get("country") or c_ip[
                    "location"
                ].get("country_code")

            if c_ip.get("dns", dict()).get("reverse_dns", dict()).get("names"):
                names = c_ip["dns"]["reverse_dns"]["names"]
                del c_ip["dns"]["reverse_dns"]
                c_ip["dns"]["hostnames"] = names

            if c_ip.get("operating_system"):
                c_ip["operating_system"] = (
                    " "
                    + c_ip["operating_system"].get("vendor", "")
                    + " "
                    + c_ip["operating_system"].get("source", "")
                    + " "
                    + c_ip["operating_system"].get("part", "")
                    + " "
                    + c_ip["operating_system"].get("cpe", "")
                )

    ip_entry = s_ip or idb_ip or dict()

    # update shodan data with censys data
    if not s_ip:
        s_ip = {
            "general-info": {},
            "services": [],
        }
    if s_ip and c_ip:
        s_ip["general-info"]["operating_system"] = c_ip.get("operating_system", "")
        s_ip["general-info"]["location"] = c_ip.get("location", "")
        s_ip["general-info"]["censys-collect-date"] = c_ip.get("last_updated_at", "")
        if c_ip.get("autonomous_system"):
            s_ip["general-info"]["ASN-name"] = c_ip.get(
                "autonomous_system", dict()
            ).get("name", "")
            s_ip["general-info"]["bgp_prefix"] = c_ip.get(
                "autonomous_system", dict()
            ).get("bgp_prefix", "")

        lupdate = s_ip["general-info"]["censys-collect-date"]
        s_ip["services"].extend(
            [
                {
                    "port": i["port"],
                    "name": i["extended_service_name"],
                    "generated-at": lupdate,
                    "version": "",
                }
                for i in c_ip["services"]
                if str(i["port"]) not in [j["port"] for j in s_ip.get("services", [])]
            ]
        )

    new_services = []
    for s in s_ip.get("services", []):
        new_services.append(
            str(s["port"]).ljust(8)
            + s["name"].ljust(20)
            + s["version"].center(25)
            + s["generated-at"].rjust(20)
        )

    s_ip["services"] = new_services
    ip_entry = s_ip

    # get the shodan IP data from the site
    now = datetime.datetime.now().timestamp()
    one_day_secs = 24 * 60 * 60
    # print(s_ip)
    if not s_ip or not s_ip.get("timestamp") or now - s_ip["timestamp"] >= one_day_secs:
        asyncio.create_task(get_shodan_ip_data(ip))

    if not idb_ip and ip:

        async def _idb_scan_and_store(ip):
            out = await shodan_internetdb_port_scan([ip])
            idb = get_target_storage().get_storage_create("shodan-internetdb-ips")
            idb.add_many(out, source="censys")

        asyncio.create_task(_idb_scan_and_store(ip))

    data = {}
    found_headlines = []
    for i in ip_entry:
        if type(ip_entry[i]) == list:
            found_headlines.append((i, ip_entry[i]))
        else:
            data[i] = ip_entry[i]

    if not ip_entry and not c_ip:
        return dict()

    c_entries = dict()
    make_org_tree("IP data", ip_entry, c_entries)

    c_entries = {
        "mode": "org-mode",
        "view-name": "shodan-target-ips",
        "buffer-name": "*current-ip-data*",
        "headline": {
            "key-foreground": "green",
            **c_entries,
        },
        "view-store": {
            "shodan-target-ips": {
                "default-directory": sys.argv[1],
            },
        },
    }

    c_entries["headline"]["entries"]["Shodan Host"] = make_org_link(
        "https://shodan.io/host/" + ip, ip
    )
    c_entries["headline"]["entries"]["ZoomEye Host"] = make_org_link(
        "https://www.zoomeye.org/searchResult?q=ip%3A%22" + ip + "%22", ip
    )
    c_entries["headline"]["entries"]["Fofa Host"] = make_org_link(
        "https://en.fofa.info/result?qbase64="
        + base64.urlsafe_b64encode(ip.encode("ascii")).decode("ascii"),
        ip,
    )
    c_entries["headline"]["entries"]["Fofa Host"] = make_org_link(
        "https://en.fofa.info/result?qbase64="
        + base64.urlsafe_b64encode(ip.encode("ascii")).decode("ascii"),
        ip,
    )
    c_entries["headline"]["entries"]["IP entry"] = ip

    c_entries["headline"]["entries"]["headlines"].append(
        elisp_make_org_headline(
            name="hosted applications",
            entries=[
                make_org_link(
                    f'elisp:(rcn-view--view-app-org-content "{app["site"]}")',
                    desc=app["site"],
                )
                for app in get_uniq_apps(s)
                if app.host == ip
            ],
        )
    )

    return c_entries
