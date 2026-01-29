
import sys
from rcn_web.viewers.emacs.utils import make_preview_tabulated_entries


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

    if create_windows: return collected
    else: return collected["window-config"]["window-1"]["entries"]


def elisp_make_js_flows_tabulated_entries(flow_storage, *args, **kwargs):
    content = flow_storage.get()
    tabl_entries = dict()

    for i in content: tabl_entries[i["id"]] = i

    if not content: return [], ""

    attrs = (("path", 100), ("flow-id", 20))

    entries, fmt = make_preview_tabulated_entries(
        tabl_entries,
        attrs,
        include_id=False,
        additional_keys=["flow-id"],
        *args,
        **kwargs
    )

    return entries, fmt
