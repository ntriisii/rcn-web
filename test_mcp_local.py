import asyncio
import sys
import os
import time
from unittest.mock import MagicMock

# Mock xxhash
class MockXXHash:
    def xxh32(self, data, seed=0):
        m = MagicMock()
        if isinstance(data, str):
            data = data.encode()
        m.intdigest.return_value = hash(data) % (2**32)
        return m


sys.modules["xxhash"] = MockXXHash()

# Ensure rcn-core and rcn-web are in the path if needed
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("../rcn-core"))
sys.path.insert(0, os.path.abspath("../pentest-utils"))

# Monkey-patching rcn_core to fix bugs locally within this script
from rcn_core.storage.bases import (
    AbstractDataStorage,
    AnnotationStorage,
    BaseSqliteStorage,
)
import rcn_core.storage.bases as bases_mod

# 1. Fix the Annotation table name bug
original_init = AbstractDataStorage.__init__


def patched_init(self, storage_name, yaml_storage_name, parent, parent_id=None):
    original_init(self, storage_name, yaml_storage_name, parent, parent_id)
    if self._storage_name == "annotations":
        self._safe_table_name = "annotations"


AbstractDataStorage.__init__ = patched_init

# 2. Fix the SQLite schema for annotations
original_init_norm = AbstractDataStorage._init_normalization_tables


def patched_init_norm(self, conn):
    # First call the original, then patch
    original_init_norm(self, conn)
    # Ensure all necessary tables exist with correct schema
    # We use DROP to ensure a clean slate for this test
    conn.execute("DROP TABLE IF EXISTS annotations")
    conn.execute("""
        CREATE TABLE annotations (
            id PRIMARY KEY,
            entry_id INTEGER,  
            parent_id INTEGER,
            source_id INTEGER,
            category TEXT,
            priority INT DEFAULT 1,
            key TEXT,
            value TEXT,
            parent_annotation_id INTEGER,
            storage_name TEXT,
            timestamp REAL
        )
    """)


AbstractDataStorage._init_normalization_tables = patched_init_norm


# 3. Fix the @cached_property length
if hasattr(AbstractDataStorage, "length"):
    del AbstractDataStorage.length


@property
def patched_length(self):
    parent_clause = ""
    if self.parent_id is not None:
        parent_clause = " where parent_id = ? "
    if not self.initialized:
        with self.get_connection() as conn:
            self._check_and_cache_schema(conn)
    with self.get_connection() as conn:
        import sqlite3

        conn.row_factory = sqlite3.Row
        res = conn.execute(
            f"select count(*) from {self._safe_table_name}{parent_clause}",
            (self.parent_id,) if self.parent_id is not None else (),
        ).fetchone()
        if res:
            return res[0]
    return 0


AbstractDataStorage.length = patched_length

# Now import the rest
from rcn_web.server_actions import scan_app, fuzz_app
import rcn_web.core.utils as web_utils

web_utils.is_in_scope = lambda site: True

from rcn_web.storage.utils import get_storage, get_app_by_site, web_match_storage
from rcn_core.storage.bases import get_storage_create, STORAGE_CACHE
from rcn_core.data_access import get_unprocessed_annotations
from rcn_core.storage.target_storage import TargetStorage
import rcn_core.globals

APP_NAME = "5dar.git.pz.epam.lvh.me:80"
CONFIG_XML = f"<config><target>https://{APP_NAME}</target></config>"


def setup_mock_storage():
    temp_dir = "/tmp/rcn_test_storage"
    if os.path.exists(temp_dir):
        import shutil

        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    target = TargetStorage("test-target", temp_dir)
    rcn_core.globals.TARGET_STORAGE = target

    from rcn_web.core.utils import add_apps

    mock_app = {
        "url": f"https://{APP_NAME}/",
        "site": APP_NAME,
        "technologies": "MockTech",
        "title": "Mock App",
        "status_code": 200,
        "method": "GET",
    }
    add_apps(target, [mock_app])
    print(f"Mock app added: {APP_NAME}")

    rcn_core.globals.YAML_FILE_CONTENT = {
        "time-events": {
            "py_mcp_ai_perform_scanning": {
                "function": "py_mcp_ai_perform_scanning",
                "require-storage": "web-apps::annotations",
                "min-entries": 1,
            }
        }
    }
    print("Mock YAML content initialized for events")
    return target


async def check_entries_ready(app_site, event_name):
    """
    Mimics the logic from ScheduledFunction.progress to check if entries
    are ready for the given event.

    This function demonstrates the metadata key structure used by the system:
    - When storage_md_get is called, it delegates to the TargetStorage with a prefixed key.
    - The key format is: "{storage_name}:{parent_id}:{event_name}:unscanned_count"
    """
    st = get_storage()
    app = get_app_by_site(st, app_site)
    if not app:
        return False

    # The annotation storage is created with the app's ID as the parent_id
    parent_id = app["id"]
    annot_storage = get_storage_create("web-apps::annotations", parent_id=parent_id)

    print(f"\n[Metadata Logic Explanation]")
    print(f"  - Storage Name: {annot_storage.storage_name}")
    print(f"  - Parent ID: {parent_id}")
    print(f"  - Event Name: {event_name}")
    print(f"  - Requested Key: '{event_name}:unscanned_count'")

    # When we call storage_md_get, it delegates to TargetStorage and constructs the full key:
    # full_key = "{storage_name}:{parent_id}:{event_name}:unscanned_count"
    # Example: "web-apps::annotations:2347361304:py_mcp_ai_perform_scanning:unscanned_count"
    count = annot_storage.storage_md_get(f"{event_name}:unscanned_count") or 0

    # Print the full key that was actually queried in the TargetStorage's metadata
    full_key = f"{annot_storage.storage_name}:{parent_id}:{event_name}:unscanned_count"
    print(f"  - Full Delegated Key in TargetStorage: '{full_key}'")
    print(f"  - Count Retrieved: {count}")

    category = "tool-scanning" if "scanning" in event_name else "tool-fuzzing"
    entries = annot_storage.get_filtered(f"category = '{category}'")
    print(f"  - Total actual entries with category '{category}': {len(entries)}")

    if count > 0:
        print(">>> Entries are READY to be operated on (metadata count > 0)")
        return True
    print(">>> No ready entries found in metadata.")
    return False


async def simulate_processing(app_site, event_name):
    st = get_storage()
    app = get_app_by_site(st, app_site)
    if not app:
        return

    category = "tool-scanning" if "scanning" in event_name else "tool-fuzzing"
    event_config = rcn_core.globals.YAML_FILE_CONTENT["time-events"][event_name]

    print(f"\n[SIMULATION] Fetching unprocessed entries for: {event_name}")

    async with get_unprocessed_annotations(
        category=category,
        scanner_name=event_name,
        event=event_config,
        target=st,
        match_storage_fn=web_match_storage,
    ) as entries:
        print(f"Fetched {len(entries)} items to process.")
        for eid, item in entries.items():
            print(f"  - Processing Entry ID: {eid}, Key: {item['entry'].get('key')}")
            # Simulate actual work...

    annot_storage = get_storage_create("web-apps::annotations", parent_id=app["id"])
    last_ts = annot_storage.storage_md_get(f"{event_name}:{category}-last-id-timestamp")
    print(f"Simulation finished. Metadata updated (last-ts): {last_ts}")


async def check_results_local(app_site, source_id, scan_type="scanning"):
    st = get_storage()
    app = get_app_by_site(st, app_site)
    if not app:
        return "App not found"

    target_storage_name = (
        "web-apps::nuclei-scanning"
        if scan_type == "scanning"
        else "web-apps::fuzzing-data"
    )
    st_obj = get_storage_create(target_storage_name, parent_id=app["id"])

    results = []
    if st_obj:
        sid = st_obj.resolve_source_id(source_id)
        if sid:
            results.extend(st_obj.get_filtered(f"source_id = {sid}"))

    if not results and st_obj:
        annotations_st = get_storage_create(
            "web-apps::annotations", parent_id=app["id"]
        )
        if annotations_st:
            key = f"scan-result:{source_id}"
            completed = annotations_st.get_filtered(f"key = '{key}'")
            if completed:
                results.append(
                    {"info": "Scan completed.", "value": completed[0].get("value")}
                )

    return f"Found {len(results)} results." if results else "No results found."


async def main():
    print("--- Setting up Mock Storage ---")
    setup_mock_storage()

    print(f"\n--- 1. Triggering Scan ---")
    from rcn_core.storage.bases import add_annotation

    app = get_app_by_site(get_storage(), APP_NAME)
    source_id = "mcp-scan-1234"
    add_annotation(
        entry_id=app["id"],
        storage_name="web-apps",
        key=source_id,
        value=f"<root><source_id>{source_id}</source_id>{CONFIG_XML}</root>",
        parent_id=app["id"],
        category="tool-scanning",
    )
    result = {"source_id": source_id}
    source_id = result.get("source_id")
    print(f"Triggered. Source ID: {source_id}")

    await asyncio.sleep(0.2)  # Allow async task to run

    print(f"\n--- 2. Checking Progress ---")
    ready = await check_entries_ready(APP_NAME, "py_mcp_ai_perform_scanning")

    print("the freaking ready state is ", ready)
    if ready:
        print(f"\n--- 3. Simulating Processing ---")
        await simulate_processing(APP_NAME, "py_mcp_ai_perform_scanning")

    print(f"\n--- 4. Mocking Results & Completion ---")
    from rcn_core.storage.bases import add_annotation

    app = get_app_by_site(get_storage(), APP_NAME)
    add_annotation(
        entry_id=app["id"],
        storage_name="nuclei-scanning",
        key=f"scan-result:{source_id}",
        value="finished",
        parent_id=app["id"],
        category="scan-result",
    )

    print(f"\n--- 5. Verifying Results via API Logic ---")
    print(f"Status: {await check_results_local(APP_NAME, source_id)}")


if __name__ == "__main__":
    asyncio.run(main())
