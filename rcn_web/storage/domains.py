
import os
import sys
import re
import validators
import datetime
import asyncio
from collections import defaultdict

import rcn_core.globals

from rcn_core.storage.target_storage import MultiTargetStorage as TargetStorage
from rcn_core.utils import storage_automation_md_get_create
from rcn_web.core.scope import get_scope_wildcards, get_config_wildcards
from rcn_core.data_access import get_unprocessed_entries, get_storage as get_storage
from rcn_web.core.utils import get_uniq_apps, web_match_storage, get_target_storage, get_target_config
from rcn_core.storage.bases import get_storage_create
from rcn_core.log import rlog

target_storage = rcn_core.globals.TARGET_STORAGE


def get_all_apps_domains(target=None):
    current_domains = set()
    st = target if target else get_target_storage()
    if not st:
        return current_domains

    for app in get_uniq_apps(st):
        if app.get('site'):
            current_domains.add(re.sub(":[0-9]+$", "", app['site']))
        if app.get('input_domain'):
            current_domains.add(re.sub(":[0-9]+$", "", app['input_domain']))

    return current_domains


def dnsx_extract_ip_info(data):
    out = defaultdict(list)
    for entry in data:
        for i in entry.get("a") or []:
            host = entry.get("host")
            if host:
                out[i].append(entry.get("host"))

    return out


def massdns_extract_ip_info(data):
    toreturn = defaultdict(list)

    for entry in data:
        q = entry["name"]
        q = q[0:-1] if q.endswith(".") else q

        for ans in entry["data"].get("answers") or []:
            d = ans["data"]
            if validators.ipv4(d) and q not in toreturn[d]:
                toreturn[d].append(q)

    return toreturn


from rcn_core.decorators import rcn_event

@rcn_event()
async def handle_unprocessed_domains(event, scheduled_md):
    scanner_name = event["name"]
    
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        new_subdomains = [i["entry"]["domain"] for i in unscanned.values()]
        if new_subdomains:
            flow = rcn_core.globals.RCN_FLOWS.get("subdomains-flow")
            if flow:
                flow_instance = flow()
                flow_instance.set_data(new_subdomains)
                await flow_instance.run()


@rcn_event()
async def check_for_new_subdomains(event, scheduled_md, matched_storages=[]):
    rcn_flows = rcn_core.globals.RCN_FLOWS
    target = event.get("target")
    st = target if target else get_target_storage()

    ctime = datetime.datetime.now().timestamp()

    # collect the last check time from the domain storage
    domains_storage = st.get_storage_create("domains")
    init_finished = domains_storage.storage_md_get("init-recon-finished")
    init_running = domains_storage.storage_md_get("init-recon-running")

    # use default value bigger than the 6 hour range to force it to run if the time
    # was not set.
    init_start_time = domains_storage.storage_md_get(
        "init-recon-started-time",
    ) or ctime + (8 * 60 * 60)

    # if start_time passed 6 hours run the flow
    if init_start_time + (6 * 60 * 60) < ctime:
        init_running = False
        init_finished = True

        domains_storage.storage_md_set("init-recon-finished", True)
        domains_storage.storage_md_set("init-recon-running", False)

    # init process didn't start on target yet.
    if init_running is None:
        return

    # if init running it will check for new subdomains
    if not init_finished or init_running == True:
        return

    # run flow
    flow = rcn_flows.get("passive-subdomain-enumeration")
    if not flow: return
    flow = flow()

    if target:
        if hasattr(flow, "set_target"):
            flow.set_target(target)
        elif hasattr(flow, "target"):
            flow.target = target

    flow.set_data([])
    out = await flow.run()

    # remove duplicate with current applications
    current_domains = get_all_apps_domains(target=target)

    # the id-fn is supposed to remove the duplicates from
    # being added to the list of domains
    domains_storage.add_many(out, source="init-process")

    # get all domains except those that has associated application already
    to_scan = [
        i["domain"] for i in domains_storage.get() if i["domain"] not in current_domains
    ]

    if to_scan:
        # run subdomains flow
        subdomains_flow = rcn_flows.get("subdomains-flow")
        if subdomains_flow:
            subdomains_flow = subdomains_flow()

            if target:
                if hasattr(subdomains_flow, "set_target"):
                    subdomains_flow.set_target(target)
                elif hasattr(subdomains_flow, "target"):
                    subdomains_flow.target = target

            subdomains_flow.set_data(to_scan)
            await subdomains_flow.run()


async def periodic_subdomain_bruteforcing(event, scheduled_md, matched_storages=[]):

    # Check if init-recon has finished before running subdomain bruteforcing
    target = event.get("target")
    target_storage = target if target else get_target_storage()
    if not target_storage:
        return

    domains_storage = target_storage.get_storage_create("domains")
    init_finished = domains_storage.storage_md_get("init-recon-finished")
    init_running = domains_storage.storage_md_get("init-recon-running")

    # If init process hasn't started or is still running, don't run bruteforcing
    if not init_finished or init_running:
        return

    rcn_flows = rcn_core.globals.RCN_FLOWS

    chunk_length = event.get("chunk-length", 5000)
    wordlist_length = event["wordlist-length"]
    rr_wordlist = event.get("rr-wordlist", "an-2m-subdomains")

    last_checked_index = scheduled_md.get("last-checked-index")
    last_checked_wildcard_index = scheduled_md.get("last-checked-index-wc") or 0

    if target:
        # Use target specific config to get wildcards
        target_name = target.get("name") if isinstance(target, dict) else getattr(target, "name", None)
        target_cfg = get_target_config(target_name) if target_name else {}
        wildcards = get_config_wildcards(
            {"scope": target_cfg.get("scope", []), "multitarget": False}
        )
    else:
        wildcards = get_scope_wildcards([])

    c_domain = last_checked_wildcard_index
    if last_checked_index and last_checked_index > wordlist_length:
        c_domain = last_checked_wildcard_index + 1
        scheduled_md["last-checked-index-wc"] = c_domain
        last_checked_index = 0

    # all wildcards have been bruteforced
    if c_domain >= len(wildcards):
        return

    domain = wildcards[c_domain]
    domain = domain.strip(".")
    begin_ww = last_checked_index or 0
    served_count = event.get("chunks-count", 8)

    rlog(
        "performing subdomain bruteforcing on ",
        domain,
        "beginning index",
        begin_ww,
        "target:",
        getattr(target, "name", "default"),
    )

    from rcn_core.time_event import start_scheduled_process
    results = await start_scheduled_process(
        (
            f"rr dbrute -d {domain} "
            f"-w {rr_wordlist}:l1 ---begin {begin_ww}"
            f" ---serve-chunks-count {served_count}"
            f" ---remote-only ---chunk-length {chunk_length}"
            " ---chunks-per-host 1 ---min-chunk-length 1000"
        ),
        timeout=event.get("timeout"),
        debug=event.get("debug"),
        name=event.get("name"),
        stdout=asyncio.subprocess.PIPE,
        shell=True,
    )

    out = results

    current_domains = get_all_apps_domains(target=target)
    to_scan = [i for i in out if i not in current_domains]
    if to_scan:
        # store the relevant data
        target_storage.get_storage_create("domains").add_many(
            to_scan, source="subdomains-bruteforcing"
        )

        rlog(f"checking live applications on {len(to_scan)}")
        flow = rcn_flows.get("check-live-http-applications")
        if flow:
            flow = flow()
            if target:
                if hasattr(flow, "set_target"):
                    flow.set_target(target)
                elif hasattr(flow, "target"):
                    flow.target = target

            flow.set_data(to_scan)

            await flow.run()

    # store back the data in the storage
    last_check = (served_count * chunk_length) + (last_checked_index or 0)
    scheduled_md["last-checked-index"] = last_check

def store_domains_in_file(domains):
    with open(os.path.join(sys.argv[1], "domains.txt"), "a+") as f:
        for d in domains:
            f.write(d + "\n")
