import time
import re
import asyncio
import functools

from urllib.parse import urlparse


def match_flow_complex(e: dict, match_value: dict, fn=None):
    value = match_value["value"]
    if fn:
        try:
            return fn(e, value)
        except Exception:
            return False

    try:
        return eval(value)
    except Exception:
        return False


def match_flow(flow: dict, match_value: dict, fn=None) -> bool:
    """
    checks if the current flow matches a `match_key` with
    value `match_value` the `match-key` correspond to a function
    to match with the value

    Args:
      flow (dict): the request response flow in a dictionary
      match_key (str): key used to get matching function
      match_value (str): value to match in matching function

    Returns:
      bool: whether or not the flow matches the function

    """

    try:
        return match_flow_complex(flow, match_value, fn) or False
    except KeyError:
        return False


def _mark_group_entry(entry, group, group_name, fn=None, indx=0):

    # check if it has been previously matched by the
    # group and don't run the match function again
    entry_id = entry["id"]
    prev_matched = group["matched-ids"]
    last_index = group["last-matched-index"]
    if indx <= last_index:
        if entry_id in prev_matched:
            if not entry.get(group_name):
                entry[group_name] = []
            # print("having an entry with matched group")
            entry[group_name].append(group["name"])
            return

    # this is considered new entry the group never
    # operated on this entry before
    else:
        if match_flow(entry, group, fn):
            if not entry.get(group_name):
                entry[group_name] = []
            entry[group_name].append(group["name"])


def mark_entry_with_match_groups(
    content, match_groups: dict, group_name: str, fn=None, indx=0
) -> dict:
    """Adds `match_group` to the list of match groups in the
    content flows if the flow is matched with match group.

    Args:
      content(dict): flow to match
      match_groups (list): list of match groups to match flows to
      group_name(str): key to give to the flow when has matched groups

    Returns:
      dict: the new content with added match groups
    """

    for entry in content:
        for group in match_groups:
            _mark_group_entry(entry, match_groups[group], group_name, fn, indx)

    return content


def compile_found_eval_expression(groups):
    for i in groups:
        val = groups[i]["value"]
        if type(val) == str:
            groups[i]["value"] = compile(val, "<string>", "eval")


def filter_flows_by_groups(content, groups: dict, fn=None, indx=0):
    compile_found_eval_expression(groups)
    return mark_entry_with_match_groups(content, groups, "filter-groups", fn, indx)


def highlight_flows_by_groups(content, groups: dict, fn=None, indx=0):
    compile_found_eval_expression(groups)
    return mark_entry_with_match_groups(content, groups, "highlight-groups", fn, indx)


def mark_flows_by_groups(content, groups: dict, fn=None, indx=0):
    compile_found_eval_expression(groups)
    return mark_entry_with_match_groups(content, groups, "mark-groups", fn, indx)
