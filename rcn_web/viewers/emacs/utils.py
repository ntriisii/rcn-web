import sys
import glob
import os
import numbers
import time
import functools
from typing import List, Any

import pentest_utils.viewers.emacs.utils as pu_utils
import pentest_utils.viewers.emacs.match_groups as pu_mg
from pentest_utils.viewers.emacs.utils import (
    ORG_KEY_FORG,
    VIEW_ID_MAPPING,
    PAGE_LIMIT,
    EntriesPaginator,
    make_tbl_id,
    make_tbl_entry,
    make_preview_tabulated_format,
    is_filtered_flow,
    compare_match_groups,
    make_proper_match_groups,
    update_mg_matched_entries,
    highlight_flows_by_groups,
    mark_flows_by_groups,
    make_org_tree,
    make_org_link,
)
from pentest_utils.storage.shared import QueryNode


# Fix for the match_fn context issues globally
def rcn_basic_match_fn(e, value):
    ctx = e.copy()
    ctx["entry"] = entry
    ctx["flow"] = entry
    # Support ~ as logical NOT for the user
    processed_value = value.replace("~", "not ")
    try:
        node = eval(
            processed_value,
            {
                "__builtins__": {
                    "bool": bool,
                    "int": int,
                    "str": str,
                    "len": len,
                }
            },
            ctx,
        )
        if isinstance(node, QueryNode):
            return node.evaluate(e)
        return bool(node)
    except:
        return False


def make_preview_tabulated_entries(
    storage_instance,
    attrs,
    refresh=True,
    match_groups=None,
    match_fn=None,
    last_id=None,
    first_id=None,
    view_id=None,
    limit=2048,
    page=None,
    after_ts=None,
    include_id=True,
    additional_keys=None,
    include_index=False,
    deep_copy=True,
    make_view_fn=None,
    extra_match_fn=None,
    extra_filter_fn=None,
    id_name="id",
    query_node: QueryNode = None,
):
    # Wrap the match_fn to ensure entry/flow context and handle errors
    orig_match_fn = match_fn

    def wrapped_match_fn(e, value):
        if orig_match_fn:
            try:
                # First try the original match_fn
                res = orig_match_fn(e, value)
                if res:
                    return True
            except:
                pass

        # Fallback to our robust match logic if original failed or was None
        return rcn_basic_match_fn(e, value)

    match_fn = wrapped_match_fn

    t0 = time.time()
    if match_groups is None:
        match_groups = dict()
    if not additional_keys:
        additional_keys = []

    # ---------------------------------------------------------
    # 1. Setup Groups & Filter Logic
    # ---------------------------------------------------------

    prev_mg = VIEW_ID_MAPPING.get(view_id, dict())
    match_groups_equal = compare_match_groups(match_groups, prev_mg)
    make_proper_match_groups(match_groups, prev_mg)

    filter_groups = match_groups.get("filter-groups", dict())
    mark_groups = match_groups.get("mark-groups", dict())
    hl_groups = match_groups.get("highlight-groups", dict())

    # ---------------------------------------------------------
    # 2. Paginator Logic (Branching: SQL vs List)
    # ---------------------------------------------------------

    # Check if we are dealing with the new AbstractStorage (SQL) or a legacy List
    is_sql_storage = hasattr(storage_instance, "get_view_data")

    batch = []
    op = "rewrite"
    new_last_id = last_id
    new_first_id = first_id

    if is_sql_storage:
        # --- SQL MODE ---

        # 1. Compile Filter Query
        # For SQL mode, filter_flows_by_groups from pentest_utils is fine
        generated_node = pu_mg.filter_flows_by_groups(None, filter_groups)
        final_query_node = query_node
        if generated_node is not None:
            final_query_node = (
                (final_query_node & generated_node)
                if final_query_node is not None
                else generated_node
            )

        # 2. Determine Fetch Direction
        fetch_after = None
        fetch_before = None

        if refresh and last_id and match_groups_equal:
            op = "append"
            fetch_after = last_id
        elif not refresh and first_id:
            op = "append"
            fetch_before = first_id
        else:
            op = "rewrite"

        use_desc_sort = True
        if fetch_after:
            use_desc_sort = False
        # 3. Execute Fetch
        batch = storage_instance.get_view_data(
            query_node=final_query_node,
            limit=limit,
            after_id=fetch_after,
            before_id=fetch_before,
            sort_desc=use_desc_sort,
        )

        if batch:
            if fetch_after:
                batch.reverse()

            # Update pagination cursors (DESC order assumed)
            new_last_id = (
                batch[0][id_name]
                if op in ["rewrite", "append"] and not fetch_before
                else new_last_id
            )
            new_first_id = (
                batch[-1][id_name]
                if op in ["rewrite", "append"] and not fetch_after
                else new_first_id
            )

            # Correction: The logic above for cursors in 'append' mode needs to be precise
            if op == "rewrite":
                new_last_id = batch[0][id_name]
                new_first_id = batch[-1][id_name]
            elif op == "append":
                if fetch_after:
                    new_last_id = batch[0][id_name]  # Top grew
                if fetch_before:
                    new_first_id = batch[-1][id_name]  # Bottom grew

    else:
        # --- LEGACY LIST MODE ---

        # 1. Setup Paginator
        # Assuming storage_instance is a list/dict of entries
        tbl_d = storage_instance
        if not isinstance(tbl_d, list) and isinstance(tbl_d, dict):
            # If dict, convert keys to list (assuming keys are IDs)
            tbl_d = list(tbl_d.keys())

        entries_generator = EntriesPaginator(
            tbl_d, last_id, first_id, refresh, match_groups_equal
        )

        # 2. Generate Pages Loop
        # For legacy, we iterate through the generator until we fill the limit
        # OR strictly follow the paginator batching

        rm_flt = functools.partial(
            is_filtered_flow, filter_keys=list(filter_groups.keys())
        )

        for pg_batch in entries_generator.generate_pages(
            limit if limit < 1000 else 512
        ):
            if len(batch) >= limit:
                break

            # Resolve actual objects if paginator yielded IDs
            resolved_batch = []
            if not isinstance(storage_instance, list):
                for i in pg_batch:
                    if i in storage_instance:
                        resolved_batch.append(storage_instance[i])
            else:
                resolved_batch = pg_batch

            if after_ts:
                resolved_batch = [
                    i for i in resolved_batch if i.get("timestamp", 0) > after_ts
                ]

            # Apply Legacy Filtering (Python side)
            # FIX: Use "filter-groups" instead of "mark-groups" for filtering
            resolved_batch = pu_mg._apply_highlight_logic_py(
                resolved_batch, filter_groups, "filter-groups", match_fn
            )
            resolved_batch = list(filter(rm_flt, resolved_batch))

            batch.extend(resolved_batch)

        op = entries_generator.op
        new_last_id = entries_generator.last_id
        new_first_id = entries_generator.first_id

    if not batch:
        return {
            "entries": [],
            "op": "nothing",
            "last-id": new_last_id,
            "first-id": new_first_id,
        }, ""

    # ---------------------------------------------------------
    # 3. Post-Processing (Marking / Highlighting)
    # ---------------------------------------------------------

    attrs = tuple((*i, None, None) for i in attrs)
    first_entry_raw = batch[0]
    first_entry_cols = make_tbl_entry(first_entry_raw, attrs)
    if not include_id:
        first_entry_cols = first_entry_cols[1:]

    marking_took = 0
    t1 = time.time()

    if extra_filter_fn:
        batch = list(filter(extra_filter_fn, batch))

    # Apply Marking and Highlighting (Client-side evaluation)
    batch = mark_flows_by_groups(batch, mark_groups, match_fn, 0)
    batch = highlight_flows_by_groups(batch, hl_groups, match_fn, 0)

    marking_took += time.time() - t1

    # Update Metadata caches
    update_mg_matched_entries(mark_groups, "mark-groups", batch, id_name)
    update_mg_matched_entries(filter_groups, "filter-groups", batch, id_name)
    update_mg_matched_entries(hl_groups, "highlight-groups", batch, id_name)

    if extra_match_fn:
        [extra_match_fn(e) for e in batch]

    collected_entries = [
        {
            "id": make_tbl_id(i.get(id_name)),
            "entry": [
                *make_tbl_entry(i, attrs, additional_keys),
                i.get("highlight-groups", []),
            ],
            "mark-groups": i.get("mark-groups", []),
            "highlight-groups": i.get("highlight-groups", []),
        }
        for i in batch
    ]

    # Cleanup
    for e in batch:
        if e.get("obj"):
            del e["obj"]
        for g in ("match-groups", "mark-groups", "filter-groups"):
            if e.get(g):
                del e[g]

    # ---------------------------------------------------------
    # 4. Final Formatting
    # ---------------------------------------------------------

    tbl_format = make_preview_tabulated_format(
        attrs=attrs,
        first_entry=first_entry_cols,
        include_id=include_id,
        additional_keys=additional_keys,
    )

    entries_obj = dict()
    entries_obj["entries"] = collected_entries
    entries_obj["op"] = op
    entries_obj["last-id"] = new_last_id
    entries_obj["first-id"] = new_first_id

    VIEW_ID_MAPPING[view_id] = match_groups

    print("whole process took:", time.time() - t0)
    print("marking took:", marking_took)

    return entries_obj, tbl_format


# Monkeypatch the original pu_utils so other modules in rcn_web get the fix
pu_utils.make_preview_tabulated_entries = make_preview_tabulated_entries


def elisp_make_basic_tabulated_entries(dstorage, attrs=None, *args, **kwargs):
    # MAYBE: use a sample
    entries = dstorage.get()
    if not entries:
        return [], ""

    first_entry = entries[0]

    # check if the entry is dict or not if not return very basic view
    if type(first_entry) is list:
        tabulated_entries, tabulated_format = make_preview_tabulated_entries(
            storage_instance=[{"entry": i[0]} for i in entries],
            attrs=(("entry", 100),),
            *args,
            **kwargs,
        )

    elif type(first_entry) in (str, int):
        tabulated_entries, tabulated_format = make_preview_tabulated_entries(
            storage_instance=[{"entry": i} for i in entries],
            attrs=(("entry", 100),),
            *args,
            **kwargs,
        )

    else:
        # collect keys from the first entry
        keys_to_show = []
        max_keys = 6
        for key in first_entry:
            if key in ["id", "timestamp"]:
                continue
            if len(keys_to_show) >= max_keys:
                break
            val = first_entry[key]
            if type(val) == str and len(val) < 300:
                keys_to_show.append(key)
            elif type(val) == list and len(", ".join(str(i) for i in val)) > 300:
                keys_to_show.append(key)
            elif type(val) == int:
                keys_to_show.append(key)

        # make the attrs string split the view between the entries
        padding_per_entry = len(keys_to_show) // 300

        keys_to_show.insert(0, "id")
        attrs = tuple((i, padding_per_entry) for i in keys_to_show)
        tabulated_entries, tabulated_format = make_preview_tabulated_entries(
            storage_instance=entries,
            attrs=attrs,
            include_id=False,
            *args,
            **kwargs,
        )

    return tabulated_entries, tabulated_format


def elisp_make_basic_storage_view(dstorage, *args, **kwargs):
    tabulated_entries, tabulated_format = elisp_make_basic_tabulated_entries(
        dstorage, *args, **kwargs
    )

    return {
        "window-config": {
            "window-1": {
                "buffer-name": "*generic-entries*",
                "mode": "tabulated-list-mode",
                "tabulated-format": tabulated_format,
                "entries": tabulated_entries,
                "navigate-fn": "rcn-view--basic-navigate-fn",
                "refresh-fn": f'(lambda () (interactive) (rcn-view--basic-refresh "{dstorage.storage_name}"))',
                "view-store": {"basic-data": {"storage-name": dstorage.storage_name}},
            },
            "window-2": {
                "buffer-name": "*generic-entries-view*",
                "mode": "org-mode",
                "entries": {},
            },
            "orientation": "horizontal",
            "scale": 0.6,
        },
    }


def elisp_make_basic_data_preview(dstorage, *args, **kwargs):
    content = dict()

    content["data Length"] = dstorage.length

    return content


def elisp_make_org_headline(name, entries, push_btn=None, storage_name=None):
    headline = {
        "entries": {},
        "name": name,
    }
    if push_btn:
        headline["push-btn-fn"] = push_btn
    elif storage_name:
        headline["push-btn-fn"] = (
            f'(lambda () (interactive) (rcn-view--basic-push-btn-with-storage "{storage_name}"))'
        )
    else:
        headline["push-btn-fn"] = "rcn-view--basic-push-btn"

    if type(entries) == dict:
        for key, value in entries.items():
            headline["entries"][key] = {"value": value, "key-foreground": ORG_KEY_FORG}

    elif type(entries) == list:
        headline["entries"][name] = [str(i) for i in entries]

    return headline


def basic_match_fn(e, value):
    return rcn_basic_match_fn(e, value)


NOTES_CONTENT = dict()
NOTES_READ = False


def read_notes_files():
    global NOTES_CONTENT, NOTES_READ

    if NOTES_READ:
        return

    # read the files
    for file in glob.glob(os.path.join(sys.argv[1], "app-notes/*.org")):
        with open(file, "r") as f:
            NOTES_CONTENT[file.split("/")[-1]] = f.read()

    NOTES_READ = True


def get_app_notes(site):
    return NOTES_CONTENT.get(site + ".org")


def make_basic_dict_entry_view(entry):
    entry_data = dict()
    make_org_tree("Basic Entry view", entry, entry_data)

    return entry_data
