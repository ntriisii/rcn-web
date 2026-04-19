import datetime
import os
import re
import sys
import time
import orgparse
import pathlib
import datetime

import rcn_core.globals
from rcn_web.viewers.emacs import refresh

import pentest_utils.viewers.emacs.utils as pu_utils
from pentest_utils.storage.shared import entry as entry_proxy, QueryNode


def rcn_basic_match_fn(e, value):
    # Ensure consistent fields for evaluation
    if "status" in e and "status_code" not in e:
        e["status_code"] = e["status"]
    elif "status_code" in e and "status" not in e:
        e["status"] = e["status_code"]

    ctx = e.copy()
    ctx["entry"] = entry_proxy
    ctx["flow"] = entry_proxy

    # Support ~ as logical NOT for the user
    processed_value = str(value).replace("~", "not ")
    try:
        res = eval(
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

        if isinstance(res, QueryNode):
            return res.evaluate(e)
        return bool(res)
    except:
        return False


# Monkeypatch to provide robust matching logic
pu_utils.basic_match_fn = rcn_basic_match_fn

from pentest_utils.viewers.emacs.utils import (
    make_org_link,
    make_preview_tabulated_entries,
    basic_match_fn,
    read_notes_files,
    NOTES_CONTENT,
    ORG_KEY_FORG,
    elisp_make_basic_storage_view,
    make_basic_dict_entry_view,
    get_app_notes,
    elisp_make_basic_data_preview,
)


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


from .ip import preview_ip_data
from .dorks import arrange_dorks_view, arrange_dorks_preview
from .dorks import arrange_google_dorks_views
from .dorks import arrange_github_dorks_views
from .dorks import arrange_shodan_dorks_views

from rcn_web import storage
from rcn_web.core.utils import (
    get_storage,
    get_target_storage,
    get_uniq_apps,
    get_app_by_site,
)
from rcn_web.core.scope import get_scope_wildcards
from rcn_core.storage.bases import (
    get_storage_create,
    add_annotation as global_add_annotation,
)

# Cache for TODOs data with file modification times
TODOS_CACHE = {}


def get_cached_todos_status(app):
    """
    Get cached TODOs status for an app.
    Returns a string in the format "completed/total" or with green color if all completed.
    """
    try:
        st_list = get_storage_create("web-apps::annotations", parent_id=app["id"])
        if not st_list:
            return "0/0"
        todos = st_list[0].get_filtered("key LIKE 'todo%'")
        if not todos:
            return "0/0"

        total_todos = len(todos)
        # Assuming TODO items starting with "DONE" are completed.
        # Adjust logic if status is stored differently.
        completed_todos = len(
            [t for t in todos if str(t["value"]).strip().upper().startswith("DONE")]
        )

        result = f"{completed_todos}/{total_todos}"
        if total_todos == completed_todos and total_todos > 0:
            return {"value": result, "fg": "green"}

        return result
    except Exception:
        return "0/0"


def elisp_view_app_annotations(app_id):
    app = get_app_by_site(get_target_storage(), app_id)
    if not app:
        return {}
    app_name = app["site"]

    st_list = get_storage_create("web-apps::annotations", parent_id=app["id"])
    annotations = st_list[0].get_all_entries() if st_list else []

    tabulated_format = [
        ["id", 15, True],
        ["key", 15, True],
        ["value", 80, True],
    ]

    tabulated_entries = []
    for a in annotations:
        tabulated_entries.append(
            [str(a["id"]), [str(a["id"]), str(a["key"]), str(a["value"])]]
        )

    return {
        "window-config": {
            "window-1": {
                "buffer-name": "*app-annotations-entries*",
                "mode": "tabulated-list-mode",
                "tabulated-format": tabulated_format,
                "entries": tabulated_entries,
                "storage-name": "annotations",
                "is-target-storage": False,
                "view-store-name": "web-apps::annotations",
            }
        },
        "view-store": {
            "web-apps::annotations": {
                "app-name": app_name,
                "default-directory": sys.argv[1],
            }
        },
    }


def elisp_view_app_todos(app_id):
    app = get_app_by_site(get_target_storage(), app_id)

    if not app:
        return {}
    app_name = app["site"]

    st_list = get_storage_create("web-apps::annotations", parent_id=app["id"])
    todos_entries = st_list[0].get_filtered("key LIKE 'todo%'") if st_list else []
    todos = [f"- {t['value']}" for t in todos_entries]

    return {
        "buffer-name": f"*todos-{app_name}*",
        "mode": "org-mode",
        "headline": {"name": f"TODOs for {app_name}", "entries": {"TODOs": todos}},
        "view-store": {
            "todos-data": {},
            "default-directory": sys.argv[1],
        },
    }


def elisp_view_target_apps(target, match_groups=None, create_windows=True, **kwargs):
    if not match_groups:
        match_groups = dict()

    collected = dict()
    t1 = time.time()
    tabulated_entries, tabulated_format = elisp_make_target_tabulated_entries(
        target, match_groups, **kwargs
    )

    # tabulated_entries, tabulated_format = elisp_view_target_gen_test()
    collected["window-config"] = {
        "window-1": {
            "buffer-name": "*app-entries*",
            "mode": "tabulated-list-mode",
            "tabulated-format": tabulated_format,
            "entries": tabulated_entries,
            "sort-key": 11,
            "storage-name": "web-apps",
            "is-target-storage": True,
            "navigate-fn": "rcn-view-app",
            "select-fn": "rcn-view-open-in-browser",
            "refresh-fn": "rcn-view--apps-refresh",
            "view-store-name": "web-apps",
            "key-bindings": [["gd", "rcn-apps-toggle-disable-selected"]],
            "buffer-store": {"parent_id": getattr(target, "id", None)},
        },
        "window-2": {
            "buffer-name": "*current-app-data*",
            "mode": "org-mode",
            "entries": {},
        },
        "orientation": "horizontal",
        "scale": 0.4,
    }

    collected["view-store"] = {
        "apps-data": {
            "tabulated-data": {"get-ids-url": "http://localhost:8023/getApp"}
        },
        "default-directory": sys.argv[1],
        "parent-storage": "targets",
        "current-view": 1,
    }

    print("took: ", time.time() - t1)

    if create_windows:
        return collected
    else:
        return collected["window-config"]["window-1"]["entries"]


def elisp_make_target_tabulated_entries(target, match_groups=None, **kwargs):
    if match_groups is None:
        match_groups = dict()

    def apps_match_fn(e, value):
        app = e.get("obj")
        if app:
            e["notes"] = NOTES_CONTENT.get(app["site"] + ".org", "")

        return basic_match_fn(e, value)

    # read_notes_files()

    t1 = time.time()

    apps = get_uniq_apps(target)
    if not apps:
        return [], ""

    # TODO: vulns, fuzzing, URL storage, TODOs, storage numbers in the tabulated entries
    attrs = (("site", 20), ("port", 3), ("title", 15), ("status_code", 3))
    st_attrs = (
        ("fuzzing", 3),
        ("scanning", 3),
        ("src found", 3),
        ("secrets", 3),
        ("js flows", 3),
        ("js", 3),
    )

    storage_mapping = {
        "src found": "app-links",
        "fuzzing": "fuzzing-data",
        "scanning": "nuclei-scanning",
        "secrets": "trufflehog-secrets",
        "js flows": "js-flows",
        "js": "js-secrets",
    }

    data_collect_fn_src_mapping = {
        "app-links": "crawl_application",
        "fuzzing-data": "application_fuzzing",
        "nuclei-scanning": "nuclei_scan_apps",
    }

    tabl_entries = {}
    for app in apps:
        tbl = {}
        tbl["id"] = str(app["id"])
        for attr in attrs + (("scheme", 0), ("url", 0)):
            tbl[attr[0]] = app[attr[0]]

        # arrange sources data
        for attr in st_attrs:
            s_name = storage_mapping.get(attr[0])
            if not s_name:
                continue
            src_list = get_storage_create("web-apps::" + s_name, parent_id=app["id"])
            if src_list:
                src = src_list[0]
                l = src.length
                v = l
                tbl[attr[0]] = v
            else:
                tbl[attr[0]] = 0

        # calculate TODOs status using cache
        tbl["todos"] = get_cached_todos_status(app)

        tbl["at"] = app["timestamp"]
        tbl["obj"] = app

        tabl_entries[tbl["id"]] = tbl

    # include more attrs
    attrs = (("todos", 4),) + attrs + st_attrs + (("at", 4),)

    _entries = list(tabl_entries.values())

    class _ListView:
        __slots__ = ("data", "length")

        def __init__(self, d):
            self.data = d
            self.length = len(d)

        def get_view_data(
            self,
            query_node=None,
            limit=100,
            after_id=None,
            before_id=None,
            sort_desc=True,
            sort_by=None,
        ):
            res = self.data
            if query_node is not None:
                res = [e for e in res if query_node.evaluate(e)]
            if after_id is not None:
                idx = next(
                    (i for i, e in enumerate(res) if str(e.get("id")) == str(after_id)),
                    -1,
                )
                if idx != -1:
                    res = res[idx + 1 :]
            elif before_id is not None:
                idx = next(
                    (
                        i
                        for i, e in enumerate(res)
                        if str(e.get("id")) == str(before_id)
                    ),
                    -1,
                )
                if idx != -1:
                    res = res[:idx]
            if sort_desc:
                res = res[::-1]
            return res[:limit]

    return make_preview_tabulated_entries(
        _ListView(_entries),
        attrs,
        match_groups=match_groups,
        match_fn=apps_match_fn,
        include_index=True,
        additional_keys=["scheme", "url"],
        **kwargs,
    )


storages_push_btn_mapping = {
    "app-links": "rcn-view-url-sources-get-views",
    "nuclei-scanning": "rcn-view--get-vulns",
    "fuzzing-data": "rcn-view--get-fuzzing",
}


def elisp_make_target_view_data():
    global storages_push_btn_mapping

    target_vars = rcn_core.globals.YAML_FILE_CONTENT["target-data-variables"]

    google = arrange_google_dorks_views()
    github = arrange_github_dorks_views()
    shodan = arrange_shodan_dorks_views()

    st = get_target_storage()
    org_entries = {
        "Apps count": len(get_uniq_apps(st)),
        "IPs count": st.get_storage_create("found-ips").length,
    }

    for ds in get_target_storage().data_storages_names:
        s = get_target_storage()[ds]
        # TODO: change here
        if not hasattr(s, "_storage_metadata"):
            s._storage_metadata = dict()

    data = {
        "window-config": {
            "window-1": {
                "buffer-name": "*target-data*",
                "mode": "org-mode",
                "headline": {
                    "name": "Target Data",
                    "key-foreground": "red",
                    "entries": {
                        **org_entries,
                        "headlines": [
                            elisp_make_org_headline(
                                name="Google Dorks",
                                entries={},
                                push_btn="rcn-view-target-google-dorks",
                            ),
                            elisp_make_org_headline(
                                name="Github Dorks",
                                entries={},
                                push_btn="rcn-view-target-github-dorks",
                            ),
                            elisp_make_org_headline(
                                name="Shodan Dorks",
                                entries={},
                                push_btn="rcn-view-target-shodan-dorks",
                            ),
                            *[
                                elisp_make_org_headline(
                                    name=" ".join(
                                        i
                                        for i in get_target_storage()[
                                            ds
                                        ].storage_name.split("-")
                                    ),
                                    entries=get_target_storage()[ds].get_data_preview(),
                                    storage_name=get_target_storage()[ds].storage_name,
                                )
                                for ds in get_target_storage().data_storages_names
                            ],
                        ],
                    },
                },
                "view-store": {
                    "target-data": {
                        "scope-sites": " ".join(
                            "site:*" + i.strip("*").strip(".")
                            for i in get_scope_wildcards([])
                        ),
                        "github-org-data": target_vars.get("github-org-data", ""),
                        "ssl-org-data": target_vars.get("ssl-org-data", ""),
                        "whois-org-data": target_vars.get("whois-org-data", ""),
                        "default-directory": sys.argv[1],
                    }
                },
            },
            "window-2": {
                "mode": "org-mode",
                "buffer-name": "*Dorks*",
                "entries": {},
            },
            "orientation": "horizontal",
        },
    }

    return data


def _app_collect_notes(path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path.as_posix(), "w") as f:
            f.write("#+TODO: TODO DOING | DONE \n")

    notes_content = orgparse.load(path.as_posix())

    # collect TODOs
    todos = []
    if notes_content.children:
        todos_content = [i for i in notes_content.children if i.heading == "TODOs"]

        if todos_content:
            # Transform subheadings under TODOs to list items with TODO keyword
            for item in todos_content[0].children:
                todo_status = item.todo or "TODO"
                todos.append("- " + todo_status + " " + item.heading)
            # todos.insert(0, "*** TODOs")

        # Include application notes inside App TODOs section as list items
        # collect content from all other headings as list items
        app_notes = []

        n_content = [i for i in notes_content.children if i.heading != "TODOs"]
        for heading in n_content:
            # Add the main heading as a list item
            app_notes.append("- App Note: " + heading.heading)
            # Also add content from its subheadings
            for subheading in heading.children[:4]:  # limit to first 4 children
                app_notes.append("- " + subheading.heading)
                # Process the content of the subheading
                for content_line in subheading.body.split("\n"):
                    if content_line.strip() and not content_line.startswith(
                        "*"
                    ):  # Skip heading lines
                        app_notes.append("- " + content_line.strip())

        # Combine todos and app notes under the TODOs section
        all_items = todos + app_notes
        # if all_items: all_items.insert(0, "*** TODOs")

        return all_items

    return []


def elisp_make_app_view_data(app):
    global storages_push_btn_mapping

    app_path = sys.argv[1]
    path = pathlib.Path(os.path.join(sys.argv[1], "app-notes/", app["site"] + ".org"))

    # app dorks
    app_url = app["scheme"] + "://" + re.sub(":[0-9]+", "", app["site"])
    dork = f"inurl:{app_url}"

    st_annot_list = get_storage_create("web-apps::annotations", parent_id=app["id"])
    st_annot = st_annot_list[0] if st_annot_list else None
    annotations = (
        [f"- {a['key']}: {a['value']}" for a in st_annot.get_all_entries()[:10]]
        if st_annot
        else []
    )

    app_data_raw = {
        "id": app["id"],
        "tech": app.get("technologies", ""),
        "input": app.get("input_domain", ""),
        "site": app["site"],
        "host": app["host"],
        "port": str(app["port"]),
        "scheme": app["scheme"],
        # "app-notes-path": path.as_posix(),
        # "app-path": app_path,
    }

    ip_entry_fn = 'elisp:(rcn-view-show-org-ip-entry "{ip}")'
    app_data = {
        "IP entry": make_org_link(ip_entry_fn.format(ip=app["host"]), app["host"]),
        "Tech": app.get("technologies", ""),
        "Tags": app.get("tags", ""),
        "browse Site": make_org_link(
            app["scheme"] + "://" + app["site"] + "/", app["site"]
        ),
        "browse URL": make_org_link(app["url"], app["url"]),
        "browse host": make_org_link(
            app["scheme"] + "://" + app["host"] + "/", app["host"]
        ),
        "host": app["host"],
        # "disabled": app['disabled'],
        "Found At": datetime.datetime.fromtimestamp(app["timestamp"]).isoformat(),
    }

    data = {
        "mode": "org-mode",
        "view-name": "app-urls",
        "headline": {
            "name": "Application Data",
            "key-foreground": "red",
            "entries": {
                **app_data,
                "headlines": [
                    elisp_make_org_headline(
                        name="App Annotations",
                        entries=annotations,
                        push_btn="rcn-view-show-app-annotations",
                    ),
                    elisp_make_org_headline(
                        name="App Flows",
                        entries=(
                            get_storage_create(
                                "web-apps::app-flows", parent_id=app["id"]
                            )[0].get_data_preview()
                            if get_storage_create(
                                "web-apps::app-flows", parent_id=app["id"]
                            )
                            else {}
                        ),
                        push_btn="rcn-view-show-app-flows",
                    ),
                    elisp_make_org_headline(
                        name="js flows",
                        entries=(
                            get_storage_create(
                                "web-apps::js-flows", parent_id=app["id"]
                            )[0].get_data_preview()
                            if get_storage_create(
                                "web-apps::js-flows", parent_id=app["id"]
                            )
                            else {}
                        ),
                        storage_name="web-apps::js-flows",
                    ),
                    *[
                        elisp_make_org_headline(
                            name=" ".join(i for i in ds.split("-")),
                            entries=(
                                get_storage_create(
                                    "web-apps::" + ds, parent_id=app["id"]
                                )[0].get_data_preview()
                                if get_storage_create(
                                    "web-apps::" + ds, parent_id=app["id"]
                                )
                                else {}
                            ),
                            push_btn=storages_push_btn_mapping.get(ds, None),
                            storage_name="web-apps::" + ds,
                        )
                        for ds in [
                            "app-links",
                            "fuzzing-data",
                            "nuclei-scanning",
                            "js-secrets",
                            "trufflehog-secrets",
                        ]
                    ],
                    elisp_make_org_headline(
                        name="js files analysis",
                        entries={
                            "dir exists": os.path.exists(
                                os.path.join(
                                    sys.argv[1],
                                    "js",
                                    re.sub(":[0-9]+", "", app["site"]),
                                )
                            )
                        },
                        push_btn="rcn-view-show-app-js-files",
                    ),
                ],
            },
        },
        "view-store": {
            "app-data": app_data_raw,
            "default-directory": sys.argv[1],
        },
    }

    return data


def elisp_make_target_tabulated_apps_with_links(target, match_groups=None, **kwargs):
    if match_groups is None:
        match_groups = dict()

    def apps_match_fn(e, value):
        app = e["obj"]
        e["notes"] = NOTES_CONTENT.get(app["site"] + ".org", "")

        return basic_match_fn(e, value)

    read_notes_files()

    t1 = time.time()

    apps = get_uniq_apps(target)
    if not apps:
        return [], ""

    # TODO: vulns, fuzzing, URL storage, TODOs, storage numbers in the tabulated entries
    attrs = (("site", 55),)

    tabl_entries = {}
    for app in apps:
        tbl = {}
        tbl["id"] = str(app["id"])

        ## collect properties
        for attr in attrs:
            tbl[attr[0]] = app[attr[0]]

        tbl["obj"] = app
        tabl_entries[tbl["id"]] = tbl

        # count the number of links in the app
        st_links_list = get_storage_create("web-apps::app-links", parent_id=app["id"])
        tbl["links"] = st_links_list[0].length if st_links_list else 0

        # calculate TODOs status using cache
        tbl["todos"] = get_cached_todos_status(app)

    # add links and todos to the attrs
    attrs = (*attrs, ("links", 4), ("todos", 4))

    # include more attrs
    _entries = list(tabl_entries.values())

    class _ListView:
        __slots__ = ("data", "length")

        def __init__(self, d):
            self.data = d
            self.length = len(d)

        def get_view_data(
            self,
            query_node=None,
            limit=100,
            after_id=None,
            before_id=None,
            sort_desc=True,
            sort_by=None,
        ):
            res = self.data
            if query_node is not None:
                res = [e for e in res if query_node.evaluate(e)]
            if after_id is not None:
                idx = next(
                    (i for i, e in enumerate(res) if str(e.get("id")) == str(after_id)),
                    -1,
                )
                if idx != -1:
                    res = res[idx + 1 :]
            elif before_id is not None:
                idx = next(
                    (
                        i
                        for i, e in enumerate(res)
                        if str(e.get("id")) == str(before_id)
                    ),
                    -1,
                )
                if idx != -1:
                    res = res[:idx]
            if sort_desc:
                res = res[::-1]
            return res[:limit]

    return make_preview_tabulated_entries(
        _ListView(_entries),
        attrs,
        match_groups=match_groups,
        match_fn=apps_match_fn,
        include_index=True,
        **kwargs,
    )


def elisp_view_target_apps_with_links(
    target, match_groups=None, create_windows=True, **kwargs
):
    if not match_groups:
        match_groups = dict()

    collected = dict()
    t1 = time.time()
    tabulated_entries, tabulated_format = elisp_make_target_tabulated_apps_with_links(
        target, match_groups, **kwargs
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
        "view-store-name": "web-apps::app-links-data",
        "key-bindings": [
            ["gtN", "rcn-view--get-urls-page"],
            ["gtb", "rcn-view-show-in-browser-view"],
            ["gd", "rcn-view-delete-selected"],
            ["gD", "rcn-view-delete-matching-expression"],
        ],
    }
    # tabulated_entries, tabulated_format = elisp_view_target_gen_test()
    collected["window-config"] = {
        "window-1": {
            "buffer-name": "*app-entries*",
            "mode": "tabulated-list-mode",
            "tabulated-format": tabulated_format,
            "entries": tabulated_entries,
            "storage-name": "web-apps",
            "is-target-storage": True,
            "navigate-fn": "rcn-view-get-app-links",
            "select-fn": "rcn-view-open-in-browser",
            "refresh-fn": "rcn-view--apps-refresh",
            "view-store-name": "web-apps",
            "key-bindings": [["gd", "rcn-apps-toggle-disable-selected"]],
        },
        "window-2": {
            "window-config": {
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
                    }
                },
                "orientation": "vertical",
                "scale": 0.3,
            }
        },
        "orientation": "horizontal",
        "scale": 0.33,
    }

    collected["view-store"] = {
        "web-apps": {
            "tabulated-data": {"get-ids-url": "http://localhost:8023/getApp"},
            "default-directory": sys.argv[1],
        },
        "parent-storage": "targets",
    }

    print("took: ", time.time() - t1)

    if create_windows:
        return collected
    else:
        return collected["window-config"]["window-1"]["entries"]
