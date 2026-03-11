import datetime

from pentest_utils.viewers.emacs.utils import (
    basic_match_fn,
    make_preview_tabulated_entries,
)
from .nuclei_vulns import elisp_make_nuclei_vulns_tabulated_entries
from pentest_utils.viewers.emacs.match_groups import (
    parse_rule_to_node,
    evaluate_query_node,
)

from rcn_web.storage.url import *
from rcn_core.storage.bases import BasicDataStorage


def elisp_view_app_found_sources_urls(
    url_storage: "BasicDataStorage",
    create_windows=False,
    match_groups=None,
    *args,
    **kwargs,
):
    if not match_groups:
        match_groups = dict()

    print("the url storage length is ", url_storage)
    collected = dict()
    tabulated_entries, tabulated_format = elisp_make_sources_url_tabulated_entries(
        url_storage=url_storage, match_groups=match_groups, *args, **kwargs
    )

    request_buf_name = "rcn-view-req-buffer"
    response_buf_name = "rcn-view-req-buffer-response"

    url_tabl_window = {
        "buffer-name": "*app-links-entries*",
        "mode": "tabulated-list-mode",
        "tabulated-format": tabulated_format,
        "entries": tabulated_entries,
        "is-target-storage": False,
        "storage-name": "app-links",
        "navigate-fn": "rcn-view-url-navigate-fn",
        "paginate-fn": "rcn-view-url--get-next-page",
        "select-fn": "rcn-view-url-repeat-request",
        "refresh-fn": "rcn-view-url-refresh-fn",
        "view-store-name": "web-apps::app-links",
        "key-bindings": [
            ["gtN", "rcn-view--get-urls-page"],
            ["gtb", "rcn-view-show-in-browser-view"],
            ["gd", "rcn-view-delete-selected"],
            ["gD", "rcn-view-delete-matching-expression"],
        ],
        "buffer-store": {"parent_id": url_storage.parent_id},
    }

    collected["window-config"] = {
        "window-1": url_tabl_window,
        "window-2": {
            "window-config": {
                "window-1": {
                    "mode": "fundamental-mode",
                    "buffer-name": request_buf_name,
                },
                "window-2": {
                    "mode": "fundamental-mode",
                    "buffer-name": response_buf_name,
                },
                "orientation": "horizontal",
                "scale": 0.3,
            }
        },
        "orientation": "vertical",
        "scale": 0.25,
    }

    collected["view-store"] = {
        "web-apps::app-links": {
            "tabulated-data": {
                "get-ids-url": "http://localhost:8023/testing-shit",
                "response-buffer": response_buf_name,
                "request-buffer": request_buf_name,
            }
        },
        "default-directory": sys.argv[1],
        "parent-storage": "web-apps",
    }

    if create_windows:
        return collected
    else:
        return collected["window-config"]["window-1"]["entries"]


def elisp_make_sources_url_tabulated_entries(url_storage, *args, **kwargs):
    def url_match_fn(e, value):
        # Ensure consistent fields for evaluation
        if "status" in e:
            e["status_code"] = e["status"]
        elif "status_code" in e:
            e["status"] = e["status_code"]

        return basic_match_fn(e, value)

    if not url_storage:
        return [], ""

    attrs = (
        ("id", 0),
        ("path", 75),
        ("status", 4),
        ("method", 5),
        ("response-ctype", 7),
        ("title", 10),
    )

    entries, fmt = make_preview_tabulated_entries(
        url_storage,
        attrs,
        include_id=False,
        additional_keys=["flow-id"],
        match_fn=url_match_fn,
        *args,
        **kwargs,
    )

    return entries, fmt


def url_sources_preview_data(sto, page=0, reset_page_counter=False, match_groups=None):
    if match_groups is None:
        match_groups = dict()

    tr = dict()

    data_length = len(sto)
    tr["Found URLs length "] = data_length

    return tr
