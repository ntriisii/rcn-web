
import sys
from .utils import *


def elisp_view_app_nuclei_scanning(vuln_s, create_windows=False, match_groups=None, *args, **kwargs):
    
    collected = dict()
    tabulated_entries, tabulated_format = elisp_make_nuclei_vulns_tabulated_entries(
        vulns_storage=vuln_s, match_groups=match_groups, *args, **kwargs
    )
    
    tmplate_buf_name = "*nuclei-vulns-template*"
    nuclei_resp_buf_name = "*nuclei-response*"
    
    collected["window-config"] = {
        "window-1": {
            "buffer-name": "*app-vulns-entries*",
            "mode": "tabulated-list-mode",
            "tabulated-format": tabulated_format,
            "entries": tabulated_entries,
            "navigate-fn": "(lambda (template-id) (interactive) (rcn-view-vulns-view-template (elt (car (cdr (assoc template-id tabulated-list-entries))) 7 )))",
            "select-fn": "rcn-view-vulns-repeat-template",
            "refresh-fn": "rcn-view--vulns-refresh",
            "buffer-store": {"parent_id": vuln_s.parent_id},
        },
        "window-2": {
            "window-config": {
                "scale": 0.6,
                "orientation": "horizontal",
                "window-1": {
                    "mode": "fundamental-mode",
                    "buffer-name": tmplate_buf_name,
                },
                "window-2": {
                    "mode": "fundamental-mode",
                    "buffer-name": nuclei_resp_buf_name,
                },
            }
        },
        "orientation": "vertical",
        "scale": 0.3,
    }
    
    collected["view-store"] = {
        "web-apps::vuln-scanning": {
            "template-buffer-name": tmplate_buf_name,
            "response-buffer-name": nuclei_resp_buf_name,
            "default-directory": sys.argv[1],
        },
        "parent-storage": "web-apps",
    }
    
    if create_windows: return collected
    else: return collected["window-config"]["window-1"]["entries"]


def nuclei_scanning_preview_data(sto):
    data = sto.get()
    tr = dict()

    tr["All Found Vulns"] = len(data)
    for i in ["Critical", "High", "Medium", "Low", "Info"]:
        tr[f"Found {i}"] = len([j for j in data if j["severity"] == i.lower()])

    return tr


def elisp_make_nuclei_vulns_tabulated_entries(vulns_storage, match_groups, *args, **kwargs):
    
    def url_match_fn(e, value):
        severity = e["severity"]
        name = e["name"]
        tags = e["tags"]

        return eval(value)
    
    content = vulns_storage.get()
    
    if not content:
        return [], ""
    
    attrs = (
        ("template-id", 10),
        ("name", 20),
        ("description", 60),
        ("severity", 10),
        ("tags", 20),
    )
    
    entries, fmt = make_preview_tabulated_entries(
        storage_instance=vulns_storage,
        attrs=attrs,
        match_groups=match_groups,
        match_fn=url_match_fn,
        *args,
        **kwargs,
    )
    
    for i, entry in enumerate(entries["entries"][::-1]):
        entry["entry"].append(content[i]["template-path"])
    
    return entries, fmt

