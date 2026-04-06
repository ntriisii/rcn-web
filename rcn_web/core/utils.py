import re
import asyncio
import os
import sys
import json
import requests
import pathlib
import fnmatch
import validators
import aiohttp
import time
import hashlib
import xxhash

from collections import defaultdict
from bs4 import BeautifulSoup as soup
from contextlib import asynccontextmanager
from typing import Callable, Any
from multidict import MultiDict
from urllib.parse import urlparse, ParseResult


class ListStorage:
    def __init__(self, data, storage_name="list-proxy"):
        self.data = data
        self.storage_name = storage_name
        self.length = len(data)

    def get_view_data(
        self,
        query_node=None,
        limit=100,
        after_id=None,
        before_id=None,
        sort_desc=True,
    ):
        res = self.data
        if query_node is not None:
            res = [e for e in res if query_node.evaluate(e)]

        # Simple ID-based pagination for the proxy
        if after_id is not None:
            idx = -1
            for i, e in enumerate(res):
                if str(e.get("id")) == str(after_id):
                    idx = i
                    break
            if idx != -1:
                res = res[idx + 1 :]
        elif before_id is not None:
            idx = -1
            for i, e in enumerate(res):
                if str(e.get("id")) == str(before_id):
                    idx = i
                    break
            if idx != -1:
                res = res[:idx]

        if sort_desc:
            res = res[::-1]

        return res[:limit]


import rcn_core.globals
from rcn_core.decorators import rcn_event
from rcn_core.log import rlog
from rcn_core.storage.target_storage import TargetStorage
from rcn_core.storage.bases import StorageMetaData, get_storage_create, add_annotation
from rcn_core.data_access import (
    get_storage,
    get_unprocessed_entries,
    match_storage,
    get_multi_unprocessed_entries,
    get_unprocessed_annotations,
    process_new_entries_for_events,
    rr_server_running,
    can_run_bulk_commands,
    reset_scanning_data,
)

_UNIQ_APPS_CACHE = {}
_UNIQ_APPS_CACHE_TTL = 30
# --- Scope Utilities (Moved from Core) ---


def is_in_scope(asset_identifier: str):
    from rcn_web.core.scope import get_target_scope, check_domain_in_scope

    return check_domain_in_scope(asset_identifier, get_target_scope())


# --- Web App Utilities ---


def get_app_by_site(target_storage_obj, app_site: str):
    if not target_storage_obj:
        return None

    if hasattr(target_storage_obj, "targets"):
        for t in target_storage_obj.targets.values():
            app = get_app_by_site(t, app_site)
            if app:
                return app
        return None

    st = target_storage_obj.get_storage_create("web-apps")

    if st.storage_name not in st._schema_cache:
        return None

    with st.get_connection() as conn:
        query = f"SELECT * FROM {st.table_name} WHERE (site = ? OR site LIKE ?)"
        cursor = conn.execute(
            query,
            (
                app_site,
                f"{app_site}:%",
            ),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)

    return None


def get_app_by_id(target_storage_obj, app_id: str | int):
    if not target_storage_obj:
        return None

    if hasattr(target_storage_obj, "targets"):
        for t in target_storage_obj.targets.values():
            app = get_app_by_id(t, app_id)
            if app:
                return app
        return None

    st = target_storage_obj.get_storage_create("web-apps")
    if st.storage_name not in st._schema_cache:
        return None

    with st.get_connection() as conn:
        cursor = conn.execute(
            f"SELECT * FROM {st.table_name} WHERE id = ?", (int(app_id),)
        )
        row = cursor.fetchone()

        if row:
            return dict(row)

    return None


def get_apps(target_storage_obj):
    if not target_storage_obj:
        return []
    if hasattr(target_storage_obj, "targets"):
        all_apps = []
        for t in target_storage_obj.targets.values():
            all_apps.extend(get_apps(t))
        return all_apps

    apps = target_storage_obj.get_storage_create("web-apps")
    return apps.get()


def get_uniq_apps(target_storage_obj) -> "list[dict]":
    # Late import to avoid circular dependency
    from rcn_web.core.scope import get_inscope_domains

    global _UNIQ_APPS_CACHE
    ts_id = id(target_storage_obj)
    current_time = time.time()

    # if ts_id in _UNIQ_APPS_CACHE:
    #     cache_entry = _UNIQ_APPS_CACHE[ts_id]
    #     if current_time - cache_entry["timestamp"] < _UNIQ_APPS_CACHE_TTL:
    #         return cache_entry["data"]

    all_apps = get_apps(target_storage_obj)
    if not all_apps:
        return []
    # print("the freaking apps length is", len(all_apps))

    found_hashes = []
    scope_data = dict()
    storage_mapping = [
        "app-links",
        "fuzzing-data",
        "nuclei-scanning",
        "trufflehog-secrets",
        "js-flows",
        "js-secrets",
    ]
    for app in all_apps:
        chash_str = (
            str(app.get("content_length", ""))
            + str(app.get("port", ""))
            + str(app.get("host", ""))
            + str(app.get("status_code", ""))
            + str(app.get("title", ""))
        )
        chash = int.from_bytes(
            hashlib.md5(chash_str.encode("utf-8")).digest(), "little"
        )
        has_data = False
        if chash not in found_hashes:
            found_hashes.append(chash)
            has_data = True
        else:
            for st_name in storage_mapping:
                full_st_name = f"web-apps::{st_name}"
                st = get_storage_create(full_st_name, parent_id=app["id"])
                if len(st) > 0:
                    has_data = True
                    break

        if has_data:
            scope_data[app["site"]] = app

    in_scope_sites = [site for site in scope_data.keys() if is_in_scope(site)]

    found_apps = [scope_data[site] for site in in_scope_sites if site in scope_data]
    found_apps = sorted(found_apps, key=lambda x: x.get("timestamp", 0.0))

    # _UNIQ_APPS_CACHE[ts_id] = {"timestamp": current_time, "data": found_apps}
    return found_apps


def get_target_for_site(target_storage_obj, site):
    # Late import
    from rcn_web.core.scope import check_domain_in_scope

    if not hasattr(target_storage_obj, "targets"):
        return target_storage_obj

    for target in target_storage_obj.targets.values():
        scope = target.config.get("scope")
        if not scope or not isinstance(scope, dict):
            continue

        wildcards = scope.get("wildcards", [])
        urls = scope.get("urls", [])

        # Sanitize wildcards for check_domain_in_scope
        wildcards = [i.replace("*.", ".").replace("*", "") for i in wildcards]

        check_scope = {"wildcards": wildcards, "urls": urls}
        if check_domain_in_scope(site, check_scope):
            return target

    if target_storage_obj.targets:
        return list(target_storage_obj.targets.values())[0]
    return None


def add_apps(target_storage_obj, apps: "list[dict]"):
    if not apps:
        return []
    if not target_storage_obj:
        return []

    if hasattr(target_storage_obj, "targets"):
        target_groups = defaultdict(list)
        for app_data in apps:
            domain = app_data.get("input")
            if not domain:
                url = (
                    app_data.get("url")
                    or app_data.get("final_url")
                    or app_data.get("location")
                )
                if url:
                    domain = urlparse(url).hostname

            if domain:
                target = get_target_for_site(target_storage_obj, domain)
                if target:
                    target_groups[target].append(app_data)

        all_added = []
        for target, target_apps in target_groups.items():
            all_added.extend(add_apps(target, target_apps))
        return all_added

    processed_apps = []

    for app_data in apps:
        app_url = (
            app_data.get("location") or app_data.get("final_url") or app_data["url"]
        )
        app_data["url"] = app_url
        parsed = urlparse(app_data["url"])
        site = parsed.netloc
        if ":" in site:
            s, p = site.split(":")
            site = s.strip(".") + ":" + p
        site = site.strip(".")

        app_data["scheme"] = parsed.scheme
        app_data["host"] = parsed.hostname

        if "port" not in app_data:
            app_data["port"] = (
                parsed.port
                if parsed.port
                else (443 if parsed.scheme == "https" else 80)
            )

        app_data["site"] = site
        if "timestamp" in app_data:
            del app_data["timestamp"]

        tech = app_data.get("tech") or app_data.get("technologies")
        if isinstance(tech, list):
            app_data["technologies"] = ",".join(tech)
        if app_data.get("input"):
            app_data["input_domain"] = app_data.get("input")

        required_keys = [
            "title",
            "method",
            "tech",
            "status_code",
            "technologies",
            "input_domain",
            "port",
            "site",
            "host",
            "url",
            "scheme",
        ]
        app_data = {i: app_data.get(i) for i in required_keys}

        processed_apps.append(app_data)

    st = target_storage_obj.get_storage_create("web-apps")
    added = st.add_many(processed_apps)

    return added


def delete_app_by_site(target_storage_obj, site):
    if not target_storage_obj:
        return
    app = get_app_by_site(target_storage_obj, site)
    if not app:
        return

    if hasattr(target_storage_obj, "targets"):
        for t in target_storage_obj.targets.values():
            if get_app_by_site(t, site):
                delete_app_by_site(t, site)
                return

    st = target_storage_obj.get_storage_create("web-apps")
    if st.storage_name not in st._schema_cache:
        return

    with st.get_connection() as conn:
        conn.execute(f"DELETE FROM {st.table_name} WHERE id = ?", (app["id"],))
        conn.commit()


class RemoteFlowsAdapter(StorageMetaData):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        StorageMetaData.__init__(self)
        self.storage_name = "flows"
        self._cache = []
        self._fetch_lock = asyncio.Lock()
        self._max_cache_size = 10000

        # persistence of start timestamp
        self._server_start_ts = self.storage_md_get("server-start-timestamp")
        if not self._server_start_ts:
            self._server_start_ts = time.time()
            self.storage_md_set("server-start-timestamp", self._server_start_ts)
        else:
            self._server_start_ts = float(self._server_start_ts)

        self._last_fetch_ts = self._server_start_ts

    @property
    def parent_id(self):
        try:
            from rcn_core.data_access import get_storage

            ts = get_storage()
            if ts:
                return ts.id
            return 1
        except:
            return 1

    @property
    def parent_container(self):
        try:
            from rcn_core.data_access import get_storage

            return get_storage()
        except:
            return None

    def _convert_headers(self, headers):
        m = MultiDict()
        if isinstance(headers, dict):
            for k, v in headers.items():
                m.add(k, v)
        elif isinstance(headers, list):
            for h in headers:
                if len(h) > 1:
                    m.add(h[0], h[1:])
        return m

    def _process_flow_headers(self, flow):
        if "request-headers" in flow:
            flow["request-headers"] = self._convert_headers(flow["request-headers"])
        if "response-headers" in flow:
            flow["response-headers"] = self._convert_headers(flow["response-headers"])
        return flow

    def _storage_md_get_data_storage(self, requester="", count=1000, category=None):
        actual_requester = f"{requester}:{category}" if category else requester
        last_ts = self.storage_md_get(actual_requester + "-last-id-timestamp") or 0.0
        data = [f for f in self._cache if float(f.get("timestamp", 0)) > float(last_ts)]
        self.storage_md_set(actual_requester + "-last-id-index", 0)
        return data

    async def _fetch_and_update_cache(self, requester, count=100, category=None):
        pass

    @asynccontextmanager
    async def get_unprocessed_entries(self, requester, count, category=None):
        await self._fetch_and_update_cache(requester, count, category=category)
        async with super().get_unprocessed_entries(
            requester, count, category=category
        ) as unprocessed:
            for i in unprocessed:
                i["id"] = i["timestamp"]
            yield unprocessed

    async def get_flows_by_id(self, flow_ids: list):
        found_flows = []
        missing_ids = []
        cache_map = {str(f.get("timestamp")): f for f in self._cache}
        for fid in flow_ids:
            fid_str = str(fid)
            if fid_str in cache_map:
                f = cache_map[fid_str]
                if "id" not in f:
                    f["id"] = f.get("timestamp")
                found_flows.append(f)
            else:
                missing_ids.append(fid_str)
        if missing_ids:
            url = "http://localhost:8082/getEntriesByIDs"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json={"ids": missing_ids}) as resp:
                        if resp.status == 200:
                            fetched = await resp.json()
                            if fetched:
                                for f in fetched:
                                    if "id" not in f:
                                        f["id"] = f.get("timestamp")
                                    self._process_flow_headers(f)
                                    found_flows.append(f)
            except Exception as e:
                rlog(f"Error fetching flows by ID: {e}", level="error")
        return found_flows

    def add_many(self, entries):
        if not entries:
            return []

        from rcn_core.data_access import process_new_entries_for_events

        # Process headers first
        for f in entries:
            self._process_flow_headers(f)
            if "id" not in f:
                f["id"] = f.get("timestamp")

        # Sort and deduplicate
        entries.sort(key=lambda x: float(x.get("timestamp", 0)))

        max_fetched_ts = float(entries[-1].get("timestamp", 0))
        self._last_fetch_ts = max(self._last_fetch_ts, max_fetched_ts)

        new_entries = []
        if not self._cache:
            new_entries = entries
        else:
            last_cache_ts = float(self._cache[-1].get("timestamp", 0))
            new_entries = [
                f for f in entries if float(f.get("timestamp", 0)) > last_cache_ts
            ]

        if new_entries:
            self._cache.extend(new_entries)
            asyncio.create_task(process_new_entries_for_events(self, new_entries))

        return new_entries


@rcn_event()
async def fetch_remote_flows(event, scheduled_md):
    adapter = RemoteFlowsAdapter.get_instance()
    from rcn_core.time_event import TimeEvent

    consumers = [
        fn
        for fn in TimeEvent()._dispatch_fns
        if fn.event and fn.event.get("require-storage") == "flows"
    ]
    if not consumers:
        # Cleanup if no consumers
        if len(adapter._cache) > adapter._max_cache_size:
            adapter._cache = adapter._cache[-adapter._max_cache_size :]
        return

    # 1. Update last-id-timestamp for events that have 0
    for fn in consumers:
        c = fn.fn_name
        ts = adapter.storage_md_get(c + "-last-id-timestamp")
        if ts is None or float(ts) == 0:
            adapter.storage_md_set(
                c + "-last-id-timestamp", adapter._server_start_ts - 0.001
            )

    # 2. Find min timestamp
    timestamps = []
    for fn in consumers:
        ts = adapter.storage_md_get(fn.fn_name + "-last-id-timestamp")
        timestamps.append(float(ts) if ts is not None else adapter._server_start_ts)

    min_ts = min(timestamps) if timestamps else adapter._server_start_ts

    # 3. Fetch from proxy if needed
    # We fetch flows after the latest one we have in cache
    fetch_ts = adapter._last_fetch_ts

    async with adapter._fetch_lock:
        url = "http://localhost:8082/GetFlowsAfterTimestmp"
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as session:
                async with session.get(
                    url,
                    params={
                        "timestamp": fetch_ts,
                        "count": 1000,
                    },
                ) as resp:
                    if resp.status == 200:
                        flows = await resp.json()
                        if flows:
                            adapter.add_many(flows)
        except aiohttp.ClientConnectorError:
            # Silently skip if proxy isn't running - this is a periodic event
            pass
        except Exception as e:
            rlog(f"Error fetching remote flows: {e}", level="error")

    # 4. Cleanup cache: keep only flows with T > min_ts (or at least server start)
    adapter._cache = [
        f
        for f in adapter._cache
        if float(f.get("timestamp", 0)) > min(min_ts, adapter._server_start_ts)
    ]


def web_match_storage(match_str, target=None):
    if match_str == "flows":
        st = RemoteFlowsAdapter.get_instance()
        return [{"storage": st, "parent": get_storage()}]

    current_storage = target if target else get_storage()
    if hasattr(current_storage, "targets") and target is None:
        found_storages = []
        for tname, t in current_storage.targets.items():
            if tname == "__multi_target__":
                continue
            found_storages.extend(web_match_storage(match_str, target=t))
        return found_storages

    parts = match_str.split("::")
    is_annotations = parts[-1] == "annotations"
    if is_annotations:
        parts.pop()
        if not parts:
            parts = [""]
    container = parts[0]
    sub_storage_name = "::".join(parts[1:])

    if container in ["web-apps", "all-web-apps", "apps"]:
        # 1. Direct resolution fallback: if the name is a full hierarchical path,
        # try to resolve it directly from the current storage context first.
        if sub_storage_name:
            try:
                st = current_storage.get_storage_create(match_str)
                if len(st) > 0:
                    return [{"storage": st, "parent": current_storage}]
            except:
                pass

        if not sub_storage_name:
            if is_annotations:
                if container == "web-apps":
                    apps = get_uniq_apps(current_storage)
                else:
                    apps = get_apps(current_storage)

                to_return = []
                for app in apps:
                    st = current_storage.get_storage_create(
                        "web-apps", parent_id=app["id"]
                    )
                    item = {
                        "parent": app,
                        "storage": st.annotations_storage,
                        "reference_storage": st,
                    }

                    to_return.append(item)

                return to_return

            st = current_storage.get_storage_create("web-apps")
            return [{"storage": st, "parent": current_storage}]

        if container == "web-apps":
            apps = get_uniq_apps(current_storage)
        else:
            apps = get_apps(current_storage)

        if not apps and sub_storage_name:
            # Fallback: if no apps found, try to resolve the storage at the target level
            # This handles cases where apps haven't been loaded or scoped yet
            try:
                st = current_storage.get_storage_create(match_str)
                return [{"storage": st, "parent": current_storage}]
            except:
                pass

        to_return = []
        for app in apps:
            st = current_storage.get_storage_create(
                sub_storage_name, parent_id=app["id"]
            )
            item = {"parent": app, "storage": st}
            if hasattr(current_storage, "name"):
                item["target_name"] = current_storage.name
            if is_annotations:
                item["storage"] = st.annotations_storage
                item["reference_storage"] = st

            to_return.append(item)
        return to_return

    # Fallback to core
    return match_storage(match_str, target)


async def mcp_server_user_interaction(prompt: str, msg_type: str = "ai-todo") -> dict:
    from pentest_utils.web.websockets import WSConnectionManager

    try:
        ws = WSConnectionManager().get_ws()
        response = await ws.send_receive(
            data={"content": prompt, "root-dir": sys.argv[1]}, msg_type=msg_type
        )
        if response is False:
            rlog("No terminal available for WebSocket prompt.", level="error")
            return {}
        return response
    except Exception as e:
        rlog(f"Error sending prompt via WebSocket: {e}", level="error")
        return {}


def uniq_apps(data):
    uniq_apps = []
    curls = []
    for app in data:
        parsed = urlparse(app.get("final_url") or app["url"])
        u = parsed.netloc
        if parsed.scheme == "http" and parsed.port == 80:
            u = u.replace(":80", "")
        if parsed.scheme == "https" and parsed.port == 443:
            u = u.replace(":443", "")
        if u not in curls:
            uniq_apps.append(app)
            curls.append(u)
    return uniq_apps
