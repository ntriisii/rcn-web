import sys
import pprint
import random
import ctypes
import datetime
import requests

from fastapi import FastAPI
from urllib.parse import urljoin
from fastapi.requests import Request
from fastapi_utils.tasks import repeat_every
from fastapi.responses import JSONResponse, HTMLResponse

from typing import Optional

import rcn_core.globals

from rcn_web.routes import *
from rcn_web.routes.mcp_api import router as mcp_router
from rcn_web import *

# Register Actions
import rcn_web.server_actions
import rcn_core.mcp.core_actions

from rcn_core.time_event import TimeEvent
from rcn_core.globals import DUMP_TIMER
from rcn_core.storage.target_storage import TargetStorage
from rcn_core.storage.bases import get_storage_create, add_annotation
from rcn_core.log import rlog
from rcn_web.viewers.emacs.target import elisp_view_target_apps
from rcn_web.viewers.emacs.target import (
    elisp_view_target_apps_with_links,
    elisp_view_app_todos,
)
from rcn_web.viewers.emacs.flows import elisp_view_app_flows
from rcn_web.viewers.emacs.target import elisp_make_app_view_data
from rcn_web.viewers.emacs.target import elisp_make_target_view_data
from rcn_web.viewers.emacs.target import arrange_dorks_view
from rcn_web.viewers.emacs.ip import view_ip_data, elisp_make_ip_view
from pentest_utils.viewers.emacs.utils import make_basic_dict_entry_view

from rcn_web.core.scope import get_inscope_domains
from rcn_web.core.scope import get_target_scope
from rcn_web.core.utils import (
    web_match_storage,
    get_storage,
    get_uniq_apps,
    get_app_by_site,
    get_app_by_id,
)

# --- Register functions for YAML context ---
import rcn_web.core.events
import rcn_web.scanning.mcp_scanners
import rcn_web.scanning.client_side
import rcn_web.scanning.app_scans
import rcn_web.scanning.utils
import rcn_web.core.remote_flow_processor
import rcn_web.scanning.owasp
import rcn_web.viewers.emacs.target
import rcn_web.viewers.emacs.flows
import rcn_web.viewers.emacs.ip
import rcn_web.viewers.emacs.dorks
# from pentest_utils.web.rcn_helpers import get_proxy_data # commonly used in yaml

# Configure TimeEvent to use web storage matcher
TimeEvent().set_match_storage_fn(web_match_storage)

# target_storage = TargetStorage.get_target_storage()
dlls = ctypes.CDLL("libc.so.6")

# NOTE: remove the root_path or include as a cli argument
app = FastAPI(
    lifespan=rcn_core.globals.POOL_EXECUTOR,
    root_path="/new-target",
    extra={
        "middleware": []
    },  # Potential fix for websocket 403s if related to middleware
)

app.include_router(ip_router)
app.include_router(domains_router)
app.include_router(app_router)
app.include_router(storage_router)
app.include_router(test_proxy)
app.include_router(mcp_router)
app.include_router(websockets_router)


@app.on_event("startup")
@repeat_every(seconds=TimeEvent().interval, raise_exceptions=True)
async def run_time_events():
    await TimeEvent().fire()


@app.on_event("shutdown")
async def shutdown_event():
    from rcn_core.globals import cleanup

    await cleanup()


@app.get("/forceDumpData")
async def force_dump_data() -> JSONResponse:
    await get_storage().dump_data(force=True)
    return JSONResponse("success")


@app.get("/getScope")
async def get_scope(request: Request):
    return get_target_scope()


from numbers import Number
from typing import Mapping, Set
from collections import deque

ZERO_DEPTH_BASES = (str, bytes, Number, range, bytearray)


def getsize(obj_0):
    """Recursively iterate to sum size of object & members."""
    _seen_ids = set()

    def inner(obj):
        obj_id = id(obj)
        if obj_id in _seen_ids:
            return 0
        _seen_ids.add(obj_id)
        size = sys.getsizeof(obj)
        if isinstance(obj, ZERO_DEPTH_BASES):
            pass  # bypass remaining control flow and return
        elif isinstance(obj, (tuple, list, Set, deque)):
            size += sum(inner(i) for i in obj)
        elif isinstance(obj, Mapping) or hasattr(obj, "items"):
            size += sum(inner(k) + inner(v) for k, v in getattr(obj, "items")())
        # Check for custom object instances - may subclass above too
        if hasattr(obj, "__dict__"):
            size += inner(vars(obj))
        if hasattr(obj, "__slots__"):  # can have __slots__ with __dict__
            size += sum(
                inner(getattr(obj, s)) for s in obj.__slots__ if hasattr(obj, s)
            )

        return size

    return inner(obj_0)


@app.get("/getApp")
async def get_app_data(app_id):
    app = get_app_by_id(get_storage(), app_id)
    if not app:
        return JSONResponse({"error": "app not found"}, status_code=404)

    data = elisp_make_app_view_data(app)

    return JSONResponse(data)


@app.post("/getApp")
async def get_app_more_data(req: Request):
    data = await req.json()
    ids = data["ids"]
    include_all_data = data["include-all-data"]
    found_apps = []
    for i in ids:
        app = get_app_by_id(get_storage(), i)
        if not app:
            continue
        if not include_all_data:
            found_apps.append(
                {
                    "input": app.get("input_domain"),
                    "site": app["site"],
                    "host": app["host"],
                    "port": app.get("port"),
                    "scheme": app.get("scheme"),
                    "tech": app.get("tech"),
                    "url": app.get("url"),
                    "title": app.get("title"),
                    "status-code": app.get("status_code"),
                }
            )

        else:
            found_apps.append(
                {
                    "input": app.get("input_domain"),
                    "site": app["site"],
                    "host": app["host"],
                    "port": app.get("port"),
                    "scheme": app.get("scheme"),
                    "tech": app.get("tech"),
                    "url": app.get("url"),
                    "title": app.get("title"),
                    "status-code": app.get("status_code"),
                    "urls": [
                        {
                            "url": app.get("scheme", "http")
                            + "://"
                            + app["site"]
                            + i["path"],
                            **i,
                        }
                        for i in get_storage_create(
                            "web-apps::app-links", parent_id=app["id"]
                        ).get()
                    ],
                    "fuzzing-urls": [
                        {
                            "status": i["status"],
                            "url": app.get("scheme", "http")
                            + "://"
                            + app["site"]
                            + i["path"],
                        }
                        for i in get_storage_create(
                            "web-apps::fuzzing-data", parent_id=app["id"]
                        ).get()
                    ],
                    "js-flows": [
                        {
                            **i,
                            "url": app.get("scheme", "http")
                            + "://"
                            + app["site"]
                            + "/"
                            + (i.get("url") or i["path"]).lstrip("/"),
                        }
                        for i in get_storage_create(
                            "web-apps::js-flows", parent_id=app["id"]
                        ).get()
                    ],
                    "nuclei-scanning": get_storage_create(
                        "web-apps::nuclei-scanning", parent_id=app["id"]
                    ).get(),
                    "js-secrets": get_storage_create(
                        "web-apps::js-secrets", parent_id=app["id"]
                    ).get(),
                    "trufflehog-secrets": get_storage_create(
                        "web-apps::trufflehog-secrets", parent_id=app["id"]
                    ).get(),
                }
            )

    return JSONResponse(found_apps)


# TODO: change the freaking name of the function
@app.post("/getAppStorage")
async def get_app(content: Request):
    json_content = await content.json()
    match_groups = json_content.get("match-groups", dict())
    app_name = content.query_params.get("app_name", "")
    app_id = content.query_params.get("app_id")
    storage_name = content.query_params["storage_name"]

    first_id = json_content.get("first-id")
    last_id = json_content.get("last-id")
    view_id = json_content.get("view-id")
    refresh = json_content.get("refresh")
    limit = json_content.get("limit") or 2048
    create_windows = json_content.get("create-windows")

    data = dict()

    if storage_name == "target":
        data = elisp_make_target_view_data()
    elif storage_name == "dorks":
        data = arrange_dorks_view()
    elif storage_name == "web-apps":
        data = elisp_view_target_apps(
            get_storage(),
            match_groups=match_groups,
            create_windows=create_windows,
            first_id=first_id,
            last_id=last_id,
            view_id=view_id,
            refresh=refresh,
            limit=limit,
        )

    elif storage_name == "app-with-links":
        data = elisp_view_target_apps_with_links(
            get_storage(),
            match_groups=match_groups,
            create_windows=create_windows,
            first_id=first_id,
            last_id=last_id,
            view_id=view_id,
            refresh=refresh,
            limit=limit,
        )

    elif storage_name == "App-Annotations":
        data = elisp_view_app_annotations(app_id)
    elif storage_name == "App-TODOs":
        data = elisp_view_app_todos(app_id)

    # elif storage_name == "app-flows":
    #     app = get_app_by_site(get_storage(), app_id)
    #     if not app:
    #         return JSONResponse({"error": "app not found"}, status_code=404)

    #     data = elisp_view_app_flows(
    #         get_storage_create("web-apps::app-flows", parent_id=app['id']),
    #         match_groups=match_groups,
    #         create_windows=create_windows,
    #         first_id=first_id,
    #         last_id=last_id,
    #         view_id=view_id,
    #         refresh=refresh,
    #         limit=limit,
    #     )

    elif storage_name == "ip":
        # internetdb_content = get_storage().get_storage_create('shodan-internetdb-ips').get()
        # if not internetdb_content:
        #   ips = [i['ip'] for i in get_storage().get_storage_create('found-ips').get()]
        #   d = await shodan_internetdb_port_scan(ips)
        #   get_storage().get_storage_create('shodan-internetdb-ips').add_many(d, source=)

        data = view_ip_data(
            get_storage(),
            match_groups=match_groups,
            create_windows=create_windows,
            first_id=first_id,
            last_id=last_id,
            view_id=view_id,
            refresh=refresh,
            id_name="id",
            limit=limit,
        )

    elif app_id or app_name:
        app = None
        if app_id:
            app = get_app_by_id(get_storage(), app_id)
        if not app and app_name:
            app = get_app_by_site(get_storage(), app_name)

        if not app:
            return JSONResponse({"error": "app not found"}, status_code=404)

        st = get_storage_create(storage_name, parent_id=app["id"])

        if not st:
            return JSONResponse(
                {"error": "storage cannot be found in app"}, status_code=404
            )

        data = st.get_data_view(
            match_groups=match_groups,
            create_windows=create_windows,
            first_id=first_id,
            last_id=last_id,
            view_id=view_id,
            refresh=refresh,
            id_name="id",
            limit=limit,
        )

    elif not app_name and not app_id and storage_name:
        st = get_storage_create(storage_name)
        if not st:
            return JSONResponse({"error": "app not found"}, status_code=404)

        data = elisp_make_basic_storage_view(st)

    return JSONResponse(data)


@app.get("/getDataView")
async def get_data_view(entry, data_storage="app"):
    data = dict()

    if data_storage == "app":
        app = get_app_by_id(get_storage(), entry)
        if not app:
            return JSONResponse({"error": "app not found"}, status_code=404)
        data = elisp_make_app_view_data(app)

    elif data_storage == "ip":
        data = elisp_make_ip_view(entry)

    return JSONResponse(data)


@app.get("/analyzeProxy")
@app.post("/analyzeProxy")
async def analyze(req: Request):
    body = await req.body()
    headers = req.headers
    url = req.url
    method = req.method
    return JSONResponse(
        {
            "body": body.decode("utf-8"),
            "headers": dict(headers),
            "url": str(url),
            "method": method,
        },
        status_code=(200 if not random.randint(1, 20) == 10 else 429),
    )


@app.get("/getAppStorageEntryById")
async def get_entry_by_id(
    entry_id: int, storage_name: str, app_name: "Optional[str]" = None
):
    if not app_name:
        st = get_storage()[storage_name]
        if not st:
            return JSONResponse("target storage not found", status_code=404)
        data = [i for i in st.get() if i["id"] == entry_id]
        if not data:
            return JSONResponse("entry not found", status_code=404)

        e = make_basic_dict_entry_view(data[0])
        return JSONResponse(e)

    app = None
    if app_name:
        app = get_app_by_id(get_storage(), app_name)
    if not app and app_name:
        app = get_app_by_site(get_storage(), app_name)

    if not app:
        return JSONResponse({"error": "app not found"}, status_code=404)

    st = get_storage_create(storage_name, parent_id=app["id"])

    if not st:
        return JSONResponse("storage not found", status_code=404)

    data = [i for i in st.get() if i["id"] == entry_id]
    if not data:
        return JSONResponse("entry not found", status_code=404)

    e = make_basic_dict_entry_view(data[0])
    return JSONResponse(e)


@app.get("/proxySync")
async def sync_proxy():
    proxy_config = rcn_core.globals.YAML_FILE_CONTENT

    # preprocess the content file
    data = dict()
    import_files = list(proxy_config.get("import-files", []))
    import_files.extend(proxy_config.get("repeater-import-files", []))
    data["import-files"] = import_files
    data["extractors"] = proxy_config["extractors"]
    data["match-and-replace"] = proxy_config["match-and-replace"]
    data["content-filter"] = proxy_config["content-filter"]

    return JSONResponse(data)


@app.get("/getAllAnnotations")
async def get_all_annotations():
    all_annotations = []
    target = get_storage()

    # 1. Fetch annotations from relevant target-level storages
    target_storages = [
        "target",
        "dorks",
        "found-ips",
        "scheduled",
        "shodan-internetdb-ips",
    ]
    for ts_name in target_storages:
        try:
            st = target.get_storage_create(ts_name)
            annotations = st.get_annotations()
            for annotation in annotations:
                annotation["app_site"] = "target"
                annotation["source_storage"] = ts_name
                all_annotations.append(annotation)
        except:
            pass

    # 2. Iterate over all unique apps
    for app in get_uniq_apps(target):
        # a. Get annotations for the app itself (annotations)
        try:
            st_app = get_storage_create("web-apps::annotations", parent_id=app["id"])
            annotations = st_app.get_annotations()
            for annotation in annotations:
                annotation["app_site"] = app["site"]
                annotation["source_storage"] = (
                    "web-apps"  # This maps to the 'web-apps' view
                )
                all_annotations.append(annotation)
        except:
            pass

        # b. Get annotations for all data storages within the app
        # For now, use a fixed list of common app storages since app is a dict and we don't know its storages easily.
        common_app_storages = [
            "app-links",
            "js-flows",
            "fuzzing-data",
            "nuclei-scanning",
            "js-secrets",
            "trufflehog-secrets",
        ]
        for st_name in common_app_storages:
            try:
                st = get_storage_create(
                    st_name if "::" in st_name else "web-apps::" + st_name,
                    parent_id=app["id"],
                )
                annotations = st.get_annotations()
                for annotation in annotations:
                    annotation["app_site"] = app["site"]
                    annotation["source_storage"] = st_name
                    all_annotations.append(annotation)
            except:
                pass

    return JSONResponse(all_annotations)


@app.get("debug")
def debug_scanners():
    scheduled_storage = get_storage().get_storage_create("scheduled").get()

    return JSONResponse(scheduled_storage)
