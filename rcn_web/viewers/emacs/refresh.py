import copy
import typing
import time
from itertools import batched
import ctypes

from pentest_utils.viewers.emacs.match_groups import filter_flows_by_groups
from pentest_utils.viewers.emacs.match_groups import mark_flows_by_groups
from pentest_utils.viewers.emacs.match_groups import highlight_flows_by_groups

dlls = ctypes.CDLL("libc.so.6")


def check_id_in_entries(content: dict, id_):
    return id_ in content


def get_refresh_content(
    entries,
    make_view_fn,
    match_fn=None,
    last_id: "typing.Optional[str]" = None,
    match_groups: dict = dict(),
    view_id: "typing.Optional[str]" = None,
    force_reload=False,
):
    t0 = time.time()

    # include the manipulation code
    mark_groups = match_groups.get("mark-groups", dict())
    filter_groups = match_groups.get("filter-groups", dict())
    highlight_groups = match_groups.get("highlight-groups", dict())

    match_groups = {
        "mark-groups": copy.deepcopy(mark_groups),
        "highlight-groups": copy.deepcopy(highlight_groups),
        "filter-groups": copy.deepcopy(filter_groups),
    }

    batch_size = 256
    to_return = {"entries": []}
    get_updated_content = not force_reload
    id_in_entries = last_id in entries
    # start_at = get_updated_content and last_id
    # out_key = "append" if get_updated_content else "history"
    # to_return[out_key] = list()
    content_keys = list(entries.keys())
    try:
        content_keys = content_keys[content_keys.index(last_id) + 1 :]
    except ValueError:
        pass
    print("last id", last_id)
    print("keys", content_keys)
    # if not content_keys: content_keys = list(entries.keys())
    for batch in batched(content_keys, batch_size):
        # get a batch size content from the cache
        # content = get_cached_content(start_at=start_at, count=batch_size)
        # content = list(content.values())
        print("inside batching")
        if not batch:
            break
        # make batch data
        batch = [entries[i] for i in batch]
        # filter groups handling
        # if filter_groups:
        #   t1 = time.time()
        #   batch = filter_flows_by_groups(batch, filter_groups, match_fn)
        #   print("content filtering took:", time.time() - t1)
        #   # remove filtered content
        #   batch = list(
        #     filter(lambda x: len(x.get('filter-groups', [])) \
        #                         == len(filter_groups.keys()), batch)
        #   )

        # # mark and highlight content
        # t1 = time.time()
        # batch = mark_flows_by_groups(batch, mark_groups, match_fn)
        # batch = highlight_flows_by_groups(batch, highlight_groups, match_fn)

        # print("marking and highlighting took:", time.time() - t1)
        # make history view from content flows
        batch = list(map(make_view_fn, batch))
        to_return["entries"].extend(batch)

        # deallocate memory as not to run out of memory
        dlls.malloc_trim(0)

    op = "append" if content_keys and id_in_entries else "rewrite"
    op = op if not content_keys else "nothing"
    to_return["last-id"] = content_keys[-1] if content_keys else last_id
    to_return["op"] = op

    print("whole process took:", time.time() - t0)

    # update last groups
    # LAST_MATCH_GROUPS[view_id] = match_groups
    print("new content", to_return)
    return to_return
