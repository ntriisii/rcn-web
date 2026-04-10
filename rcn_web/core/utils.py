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


import rcn_core.globals
from rcn_core.decorators import rcn_event
from rcn_core.log import rlog
from rcn_core.storage.bases import (
    StorageMetaData,
    get_storage_create,
    add_annotation,
    get_target_storage,
)
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


def get_target_config(target_name: str) -> dict:
    """Return the YAML config dict for the named target."""
    targets = rcn_core.globals.YAML_FILE_CONTENT.get("targets", {})
    entry = targets.get(target_name, {})
    if not isinstance(entry, dict):
        return {}
    return entry


# --- Scope Utilities (Moved from Core) ---


def is_in_scope(asset_identifier: str):
    from rcn_web.core.scope import get_target_scope, check_domain_in_scope

    return check_domain_in_scope(asset_identifier, get_target_scope())


# --- Web App Utilities ---


def get_app_by_site(target_storage_obj, app_site: str):
    if not target_storage_obj:
        return None

    for st in target_storage_obj.get_storage_create("web-apps"):
        if st.storage_name not in st._schema_cache:
            continue
        with st.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {st.table_name} WHERE (site = ? OR site LIKE ?)",
                (app_site, f"{app_site}:%"),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
    return None


def get_app_by_id(target_storage_obj, app_id: str | int):
    if not target_storage_obj:
        return None

    for st in target_storage_obj.get_storage_create("web-apps"):
        if st.storage_name not in st._schema_cache:
            continue
        with st.get_connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {st.table_name} WHERE id = ?", (int(app_id),)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
    return None


def get_apps(target_storage_obj):
    """Collect apps across all targets."""
    if not target_storage_obj:
        return []
    all_apps = []
    for st in target_storage_obj.get_storage_create("web-apps"):
        if st:
            all_apps.extend(st.get())
    return all_apps


def get_uniq_apps(target_storage_obj) -> "list[dict]":
    from rcn_web.core.scope import check_domain_in_scope

    global _UNIQ_APPS_CACHE
    ts_id = id(target_storage_obj)
    current_time = time.time()

    if ts_id in _UNIQ_APPS_CACHE:
        cache_entry = _UNIQ_APPS_CACHE[ts_id]
        if current_time - cache_entry["timestamp"] < _UNIQ_APPS_CACHE_TTL:
            return cache_entry["data"]

    t1 = current_time
    if not target_storage_obj:
        return []

    apps_with_targets = []
    mts = get_target_storage()
    for target_data in mts.targets_storage.get():
        wa_storages = target_storage_obj.get_storage_create(
            "web-apps", parent_id=target_data["id"]
        )
        for wa in wa_storages:
            if wa:
                for app in wa.get():
                    apps_with_targets.append((app, target_data))

    if not apps_with_targets:
        return []

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

    for app, target in apps_with_targets:
        target_name = (
            target.get("name")
            if isinstance(target, dict)
            else getattr(target, "name", None)
        )
        target_cfg = get_target_config(target_name) if target_name else {}
        target_scope = target_cfg.get("scope")
        if target_scope:
            wildcards = target_scope.get("wildcards", [])
            wildcards = [i.replace("*.", "").replace("*", "") for i in wildcards]
            normalized_scope = {
                "wildcards": wildcards,
                "urls": target_scope.get("urls", []),
            }
            if not check_domain_in_scope(app["site"], normalized_scope):
                continue
        elif not is_in_scope(app["site"]):
            continue

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
                st_list = mts.get_storage_create(full_st_name, parent_id=app["id"])
                if st_list and any(s and len(s) > 0 for s in st_list):
                    has_data = True
                    break

        if has_data:
            scope_data[app["site"]] = app

    found_apps = list(scope_data.values())
    found_apps = sorted(found_apps, key=lambda x: x.get("timestamp", 0.0))

    if time.time() - t1 > 0.1:
        print(
            f"DEBUG: get_uniq_apps took {time.time() - t1:.4f}s for {len(found_apps)} apps"
        )

    _UNIQ_APPS_CACHE[ts_id] = {"timestamp": time.time(), "data": found_apps}
    return found_apps


def get_target_for_site(target_storage_obj, site):
    from rcn_web.core.scope import check_domain_in_scope

    mts = get_target_storage()
    for target_data in mts.targets_storage.get():
        config = target_data.get("config")
        scope = config.get("scope") if isinstance(config, dict) else None
        if not scope or not isinstance(scope, dict):
            continue
        wildcards = scope.get("wildcards", [])
        urls = scope.get("urls", [])
        wildcards = [i.replace("*.", ".").replace("*", "") for i in wildcards]
        check_scope = {"wildcards": wildcards, "urls": urls}
        if check_domain_in_scope(site, check_scope):
            return mts.get_target_storage(target_data["name"])

    targets = mts.targets_storage.get()
    if targets:
        return mts.get_target_storage(targets[0]["name"])
    return None


def add_apps(target_storage_obj, apps: "list[dict]"):
    if not apps:
        return []

    from rcn_web.core.scope import check_domain_in_scope

    mts = get_target_storage()

    # 1. Bulk collect targets and their scopes
    targets_data = mts.targets_storage.get()
    targets_info = []
    for target_data in targets_data:
        config = target_data.get("config")
        if not isinstance(config, dict):
            continue
        scope = config.get("scope")
        if not isinstance(scope, dict):
            continue

        wildcards = [
            i.replace("*.", ".").replace("*", "") for i in scope.get("wildcards", [])
        ]
        check_scope = {"wildcards": wildcards, "urls": scope.get("urls", [])}

        targets_info.append(
            {
                "check_scope": check_scope,
                "target_obj": mts.get_target_storage(target_data["name"]),
            }
        )

    default_target = None
    if targets_info:
        default_target = targets_info[0]["target_obj"]
    elif targets_data:
        default_target = mts.get_target_storage(targets_data[0]["name"])

    # 2. Group apps by target
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

        target = None
        if domain:
            for t_info in targets_info:
                if check_domain_in_scope(domain, t_info["check_scope"]):
                    target = t_info["target_obj"]
                    break

        if not target:
            target = default_target

        if target:
            target_groups[target].append(app_data)

    # 3. Add apps for each target
    all_added = []
    for target, target_apps in target_groups.items():
        st_list = target.get_storage_create("web-apps")
        if not st_list:
            continue

        for st in st_list:
            if st.storage_name not in st._schema_cache:
                continue

            # Deduplicate against existing apps in this target
            existing_sites = set()
            with st.get_connection() as conn:
                cursor = conn.execute(f"SELECT site FROM {st.table_name}")
                existing_sites = {row[0] for row in cursor.fetchall()}

            to_add = []
            for app in target_apps:
                site = app.get("site")
                if not site:
                    url = app.get("url") or app.get("final_url") or app.get("location")
                    if url:
                        site = urlparse(url).netloc

                if site and site not in existing_sites:
                    app["site"] = site
                    to_add.append(app)
                    existing_sites.add(site)

            if to_add:
                added = st.add_many(to_add)
                if added:
                    all_added.extend(added)
                else:
                    all_added.extend(to_add)

    return all_added


def delete_app_by_site(target_storage_obj, site):
    if not target_storage_obj:
        return
    app = get_app_by_site(target_storage_obj, site)
    if not app:
        return

    for st in target_storage_obj.get_storage_create("web-apps"):
        if st.storage_name not in st._schema_cache:
            continue
        with st.get_connection() as conn:
            conn.execute(f"DELETE FROM {st.table_name} WHERE id = ?", (app["id"],))
            conn.commit()
        return


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
            ts = get_target_storage()
            if ts:
                return ts.id
            return 1
        except:
            return 1

    @property
    def parent_container(self):
        try:
            return get_target_storage()
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

    def get_view_data(
        self,
        query_node=None,
        limit=100,
        after_id=None,
        before_id=None,
        sort_desc=True,
    ):
        res = self._cache
        if query_node is not None:
            res = [e for e in res if query_node.evaluate(e)]

        # Simple ID-based pagination (ID is timestamp)
        if after_id is not None:
            res = [e for e in res if float(e.get("timestamp", 0)) > float(after_id)]
        elif before_id is not None:
            res = [e for e in res if float(e.get("timestamp", 0)) < float(before_id)]

        if sort_desc:
            res = sorted(res, key=lambda x: float(x.get("timestamp", 0)), reverse=True)
        else:
            res = sorted(res, key=lambda x: float(x.get("timestamp", 0)))

        return res[:limit]

    def get_text_preview(self, filter=None) -> str:
        items = self.get_view_data(limit=5)
        from rcn_core.mcp.utils import format_entries_text

        header = f"Storage: {self.storage_name}\nEntries: {len(self._cache)}\n"
        return header + format_entries_text(items, self.storage_name)

    def get_text_view(self, page=1, limit=200, filter=None) -> str:
        items = self.get_view_data(limit=limit)
        from rcn_core.mcp.utils import format_entries_text

        return format_entries_text(items, self.storage_name)

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
        return [{"storage": st, "parent": get_target_storage()}]

    parts = match_str.split("::")
    is_annotations = parts[-1] == "annotations"
    if is_annotations:
        parts.pop()
        if not parts:
            parts = [""]
    container = parts[0]
    sub_storage_name = "::".join(parts[1:])

    if container in ["web-apps", "all-web-apps", "apps"]:
        # Collect apps across all targets
        mts = get_target_storage()
        if not mts:
            return []
        all_apps = []
        for target_data in mts.targets_storage.get():
            st_list = mts.get_storage_create("web-apps", parent_id=target_data["id"])
            if st_list:
                for wa in st_list:
                    if wa:
                        all_apps.extend(wa.get())

        if not sub_storage_name:
            if is_annotations:
                to_return = []
                for app in all_apps:
                    st_list = mts.get_storage_create("web-apps", parent_id=app["id"])
                    st = st_list[0] if st_list else None
                    if not st:
                        continue
                    item = {
                        "parent": app,
                        "storage": st.annotations_storage,
                        "reference_storage": st,
                    }
                    to_return.append(item)
                return to_return

            st_list = mts.get_storage_create("web-apps")
            return [{"storage": s, "parent": mts} for s in st_list if s is not None]

        to_return = []
        for app in all_apps:
            st_list = mts.get_storage_create(match_str, parent_id=app["id"])
            st = st_list[0] if st_list else None
            if not st:
                continue
            item = {"parent": app, "storage": st}
            if is_annotations:
                item["storage"] = st.annotations_storage
                item["reference_storage"] = st
            to_return.append(item)
        return to_return

    # Fallback to core matching
    return match_storage(match_str, target=target)


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
