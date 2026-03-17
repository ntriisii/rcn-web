import sys
from pentest_utils.viewers.emacs.utils import (
    make_preview_tabulated_entries,
)


def elisp_view_js_flows(
    flow_storage, create_windows=False, match_groups=None, *args, **kwargs
):
    if not match_groups:
        match_groups = dict()

    collected = dict()
    tabulated_entries, tabulated_format = elisp_make_js_flows_tabulated_entries(
        flow_storage=flow_storage, match_groups=match_groups, *args, **kwargs
    )

    request_buf_name = "rcn-view-req-buffer"
    response_buf_name = "rcn-view-req-buffer-response"

    flow_tabl_window = {
        "buffer-name": "*js-flows-entries*",
        "mode": "tabulated-list-mode",
        "tabulated-format": tabulated_format,
        "entries": tabulated_entries,
        "is-target-storage": False,
        "storage-name": "js-flows",
        "navigate-fn": "rcn-view-flow-navigate-fn",
        "paginate-fn": "rcn-view-flow--get-next-page",
        "select-fn": "rcn-view-flow-repeat-request",
        "refresh-fn": "rcn-view-flow-refresh-fn",
        "view-store-name": "web-apps::js-flows",
        "key-bindings": [
            ["gtN", "rcn-view--get-flows-page"],
            ["gtb", "rcn-view-show-in-browser-view"],
        ],
        "buffer-store": {"parent_id": flow_storage.parent_id},
    }

    collected["window-config"] = {
        "window-1": flow_tabl_window,
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
                "scale": 0.5,
            }
        },
        "orientation": "vertical",
        "scale": 0.25,
    }

    collected["view-store"] = {
        "web-apps::js-flows": {
            "tabulated-data": {
                "response-buffer": response_buf_name,
                "request-buffer": request_buf_name,
            },
            "default-directory": sys.argv[1],
        },
        "parent-storage": "web-apps",
    }

    if create_windows:
        return collected
    else:
        return collected["window-config"]["window-1"]["entries"]


def elisp_make_js_flows_tabulated_entries(flow_storage, *args, **kwargs):
    if not flow_storage:
        return [], ""

    attrs = (("path", 100), ("flow-id", 20))

    entries, fmt = make_preview_tabulated_entries(
        flow_storage,
        attrs,
        include_id=False,
        additional_keys=["flow-id"],
        *args,
        **kwargs,
    )

    return entries, fmt


def elisp_view_js_links(
    url_storage, create_windows=False, match_groups=None, *args, **kwargs
):
    if not match_groups:
        match_groups = dict()

    collected = dict()
    tabulated_entries, tabulated_format = elisp_make_js_links_tabulated_entries(
        url_storage=url_storage, match_groups=match_groups, *args, **kwargs
    )

    request_buf_name = "rcn-view-req-buffer"
    response_buf_name = "rcn-view-req-buffer-response"

    url_tabl_window = {
        "buffer-name": "*js-links-entries*",
        "mode": "tabulated-list-mode",
        "tabulated-format": tabulated_format,
        "entries": tabulated_entries,
        "is-target-storage": False,
        "storage-name": "js-links",
        "navigate-fn": "rcn-view-url-navigate-fn",
        "paginate-fn": "rcn-view-url--get-next-page",
        "select-fn": "rcn-view-url-repeat-request",
        "refresh-fn": "rcn-view-url-refresh-fn",
        "view-store-name": "web-apps::js-links",
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
        "web-apps::js-links": {
            "tabulated-data": {
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


def elisp_make_js_links_tabulated_entries(url_storage, *args, **kwargs):
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
        *args,
        **kwargs,
    )

    return entries, fmt


def js_links_preview_data(sto, page=0, reset_page_counter=False, match_groups=None):
    if match_groups is None:
        match_groups = dict()

    tr = dict()

    data_length = len(sto)
    tr["Found URLs length "] = data_length

    return tr


def elisp_view_js_secrets(
    secret_storage, create_windows=False, match_groups=None, *args, **kwargs
):
    from pentest_utils.viewers.emacs.utils import elisp_make_basic_storage_view

    return elisp_make_basic_storage_view(secret_storage, *args, **kwargs)


def js_secrets_preview_data(sto, *args, **kwargs):
    tr = dict()
    tr["Secrets count"] = len(sto)
    return tr
