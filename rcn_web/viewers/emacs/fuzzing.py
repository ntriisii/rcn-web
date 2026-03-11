import sys
from .utils import *


def elisp_view_app_fuzzing(
    fz_st, create_windows=False, match_groups=None, *args, **kwargs
):
    collected = dict()
    tabulated_entries, tabulated_format = elisp_make_fuzzing_tabulated_entries(
        fuzzing_storage=fz_st, match_groups=match_groups, *args, **kwargs
    )

    request_buf_name = "rcn-view-req-buffer"
    response_buf_name = "rcn-view-req-buffer-response"
    url_tabl_window = {
        "buffer-name": "*app-url-fuzzing-entries*",
        "mode": "tabulated-list-mode",
        "tabulated-format": tabulated_format,
        "entries": tabulated_entries,
        "refresh-fn": f"rcn-view-fuzzing-refresh-fn",
        "navigate-fn": "rcn-view-fuzzing-mitmp-view-request",
        "select-fn": "rcn-view-fuzzing-repeat-request",
        "view-store-name": "web-apps::fuzzing-data",
        "buffer-store": {"parent_id": fz_st.parent_id},
    }

    collected["window-config"] = {
        "window-1": url_tabl_window,
        "window-2": {
            "window-config": {
                "window-1": {
                    "mode": "fundamental-mode",
                    "buffer-name": response_buf_name,
                },
                "window-2": {
                    "mode": "fundamental-mode",
                    "buffer-name": request_buf_name,
                },
                "orientation": "horizontal",
                "scale": 0.3,
            }
        },
        "orientation": "vertical",
        "scale": 0.25,
    }

    collected["view-store"] = {
        "web-apps::fuzzing-data": {
            "tabulated-data": {
                "tabulated-buffer": "*app-url-fuzzing-entries*",
                "request-buffer": request_buf_name,
                "response-buffer": response_buf_name,
            }
        },
        "default-directory": sys.argv[1],
        "parent-storage": "web-apps",
    }

    if create_windows:
        return collected
    else:
        return collected["window-config"]["window-1"]["entries"]


def fuzzing_preview_data(sto):
    tr = dict()
    tr["Fuzzed URLs length"] = sto.length

    return tr


def elisp_make_fuzzing_tabulated_entries(
    fuzzing_storage, match_groups, *args, **kwargs
):
    def url_match_fn(e, value):
        path = e["path"]
        status = e["status"]

        return eval(value)

    content = fuzzing_storage.get()

    if not content:
        return [], ""

    attrs = (("id", 0), ("path", 100), ("status", 10), ("response-hash", 6))

    return make_preview_tabulated_entries(
        storage_instance=fuzzing_storage,
        attrs=attrs,
        match_groups=match_groups,
        match_fn=url_match_fn,
        include_id=False,
        *args,
        **kwargs,
    )
