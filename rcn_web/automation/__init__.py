import bisect
import copy
import hashlib
import json
import time
import datetime
import asyncio
import concurrent.futures

import rcn_core.globals

from .scheduled_tasks import *
from .burpsuite_vuln_checks import *
from .utils import automation_get_storage_data

from rcn_web.core.utils import storage
from rcn_web.storage.utils import get_storage_data
from rcn_core.log import rlog


AUTOMATION_RUNNING_RULES = []


async def automation_rules_runner(event):

    global AUTOMATION_RUNNING_RULES

    rules = storage().automation_rules
    yaml_config = rcn_core.globals.YAML_FILE_CONTENT

    async def run_automation_flow(app, storage, flow):

        return await flow.run()

    last_ran = storage().automation_data
    apps = get_uniq_apps(storage())
    now = datetime.datetime.now().timestamp()
    tasks = []
    for rule in rules:
        rule_content = rules[rule]
        interval = rule_content.get("interval", 300)
        flow = rule_content.get("run-flow", None)
        prepare_fn = rule_content.get("prepare-fn", None)
        matchers = rule_content.get("storage-matchers", [])
        enabled = rule_content.get("enabled", True)

        if not enabled:
            continue
        # don't run rules that are already running
        if rule in AUTOMATION_RUNNING_RULES:
            continue
        # don't run rules that hasn't waited intervals
        rule_last_ran = last_ran.get(rule)
        if rule_last_ran and now - rule_last_ran < interval:
            continue

        # TODO: maybe include the code of the function in the hash
        # replace objects to be able to serialize
        rule_content_to_dump = copy.deepcopy(rule_content)
        rule_content_to_dump = {
            i[0]: i[1] if not callable(i[1]) else i[1].__name__
            for i in rule_content_to_dump.items()
        }

        # used as to know if the rule has changed in the yaml
        # file so that it should rerun again on the data
        rule_content_hash = str(
            hashlib.md5(json.dumps(rule_content_to_dump).encode("utf-8")).digest().hex()
        )

        flow = rcn_core.globals.RCN_FLOWS[flow]()
        # don't bother processing rules without flows
        if not flow:
            rlog(f"automation-rule {rule} has no run flow", level="warn")
            continue

        AUTOMATION_RUNNING_RULES.append(rule)
        collected_storages = []
        t1 = time.time()
        for matcher in matchers:
            # matcher is something like this apps::.*::app-links
            try:
                storage_matcher, entries_matchers = matcher.split(" ", 1)
            except IndexError:
                rlog(f"syntax error in matcher {matcher} in {rule}")
                continue

            # collected_storages.extend()
            matched_storages = get_storage_data(storage_matcher)
            matched_storages.sort(key=lambda st: len(st), reverse=True)
            for st in matched_storages:
                if len(st) == 0:
                    continue
                indicies = get_matched_indices(
                    rule, rule_content_hash, st, entries_matchers
                )
                if not indicies:
                    continue
                collected_storages.append({"indicies": indicies, "storage": st})

        if not collected_storages:
            continue
        # check if the interval has elapsed
        data = []
        if prepare_fn:
            d = []
            for i in collected_storages:
                s = i["storage"]
                ind = i["indicies"]
                c = s.get()
                data.extend(prepare_fn([c[i] for i in ind], s))

        else:
            data = collected_storages

        # if not data: continue
        # run the flow on the application and mark it in the automation
        # in target as not to run it again
        flow.set_data(data)
        await flow.run()
        AUTOMATION_RUNNING_RULES.remove(rule)

        # set the rule in the automation data
        # NOTE: we use the storage as it will be dumped in disk
        # so that the data will be kept across sessions
        last_ran[rule] = datetime.datetime.now().timestamp()

        # update the metadata in the storage by the items that has
        # been processed
        for i in collected_storages:
            s = i["storage"]
            ind = len(s) - 1
            last = s.get()[ind]
            last_timestamp = last["timestamp"]
            last_id = last["id"]
            metadata = s.storage_md_get("__automation_rules")
            if not metadata:

                s.storage_md_set("__automation_rules", dict())
                metadata = s.storage_md_get("__automation_rules")

            metadata[rule] = {
                "last_timestamp": last_timestamp,
                "last_id": last_id,
                "automation_hash": rule_content_hash,
                "data_length": len(s),
                "last_index": len(s) - 1,
            }


# TimeEvent().add_fn(
#   fn=automation_rules_runner,
#   repeat=True,
#   interval=3,
#   internal=True
# )


def get_matched_indices(
    rule_name: str, rule_content_hash: str, st, expr: str
) -> "list[int]":

    st_automation_md = st.storage_md_get("__automation_rules") or dict()
    rule_md = st_automation_md.get(rule_name, dict())
    prev_hash = rule_md.get("automation_hash", "")
    last_ts = rule_md.get("last_timestamp", 0)
    last_index = rule_md.get("last_index", 0)
    data_length = rule_md.get("data_length", 0)
    last_id = rule_md.get("last_id")

    data = st.get()
    if prev_hash != rule_content_hash:
        print("non matching hashes")
        last_index = 0
        last_id = None
        last_ts = None

    # check if the data has been modified to try and reach
    # anywhere near a new data that has not been worked on yet.
    else:
        # get previous ids and get the index from there
        prev_ids = [i["id"] for i in data]
        try:
            last_index = prev_ids.index(last_id)
        except ValueError:
            prev_tss = [i["timestamp"] for i in data]  # will be sorted
            try:
                last_index = prev_tss.index(last_ts)
            except ValueError:
                last_index = bisect.bisect_left(prev_tss, last_ts)

    # prevent the automation from running forever on
    # storages with only 1 entry as we perceive 0
    # last_index as the storage never has been worked on
    # or data changed
    if last_index == 0 and data_length == 1 and last_id:
        return []
    # when set it as 0 it would always miss the first element
    # so we don't care about doing the first element again
    # if it has been on the first element already
    if last_index == 0:
        last_index = -1
    data = data[last_index + 1 :]

    truth_comp = compile(expr, "<string>", "eval")
    indicies = []
    for i, e in enumerate(data):
        try:
            truth = eval(truth_comp)
            if truth:
                indicies.append(i)
        except:
            continue
    # if indicies:
    #   print(f"{last_ts=}")
    #   print(f"{last_index=}")
    #   print(f"{last_id=}")
    #   print(f"{len(st.get())=}")
    #   print(f"{st_automation_md=}")

    return indicies
from .csp_bypass import *
