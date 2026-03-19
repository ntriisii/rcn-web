import asyncio
import sys
import os
import time

# Ensure rcn-core and rcn-web are in the path if needed
# (Assuming current working directory is rcn-core and rcn-web is a sibling)
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("../rcn-web"))

from rcn_web.server_actions import scan_app, fuzz_app
from rcn_web.storage.utils import get_storage, get_app_by_site
from rcn_core.storage.bases import get_storage_create, STORAGE_CACHE

APP_NAME = "5dar.git.pz.epam.lvh.me:80"
CONFIG_XML = f"<config><target>https://{APP_NAME}</target></config>"


async def check_entries_ready(app_site, event_name):
    """
    Mimics the logic from ScheduledFunction.progress to check if entries
    are ready for the given event.
    """
    st = get_storage()
    if not st:
        print("Storage not initialized")
        return False

    app = get_app_by_site(st, app_site)
    if not app:
        print(f"App {app_site} not found in storage")
        return False

    # Get the TargetStorage for this app
    # In rcn-core/web, app entries are usually in 'web-apps' storage under a TargetStorage
    # We need to find which TargetStorage contains this app.
    # Since we are using get_app_by_site, we already have the app entry.
    # The app['id'] is used as parent_id for sub-storages like annotations.

    # Check if the annotation exists
    annot_storage = get_storage_create("web-apps::annotations", parent_id=app["id"])

    # Mimic ScheduledFunction.progress: check unscanned_count metadata
    # Metadata key: {storage_name}:{parent_id}:{event_name}:unscanned_count
    # Note: st.storage_md_get handles the delegation to TargetStorage

    # We check the metadata on the 'web-apps::annotations' storage object
    # because that's what add_annotation increments.
    count = annot_storage.storage_md_get(f"{event_name}:unscanned_count") or 0

    print(f"Event: {event_name}")
    print(f"App: {app_site} (ID: {app['id']})")
    print(f"Unscanned count in metadata: {count}")

    # Check actual entries in the storage
    # get_unprocessed_annotations usually filters by category too
    category = "tool-scanning" if "scanning" in event_name else "tool-fuzzing"
    entries = annot_storage.get_filtered(f"category = '{category}'")
    print(f"Total entries with category '{category}': {len(entries)}")

    if count > 0:
        print(">>> Entries are READY to be operated on (metadata count > 0)")
        return True
    else:
        print(">>> No ready entries found in metadata.")
        return False


async def check_results_local(app_site, source_id, scan_type="scanning"):
    """
    Mimics /mcp/check_scan_results API endpoint logic.
    """
    st = get_storage()
    app = get_app_by_site(st, app_site)
    if not app:
        return f"App {app_site} not found"

    results = []

    target_storage_name = None
    if scan_type == "scanning":
        target_storage_name = "web-apps::nuclei-scanning"
    elif scan_type == "fuzzing":
        target_storage_name = "web-apps::fuzzing-data"
    else:
        return f"Invalid scan_type: {scan_type}"

    # Check for data
    st_obj = get_storage_create(target_storage_name, parent_id=app["id"])
    if st_obj:
        sid = st_obj.resolve_source_id(source_id)
        if sid:
            entries = st_obj.get_filtered(f"source_id = {sid}")
            if entries:
                results.extend(entries)

    # If no results found, check for completion annotation
    if not results and st_obj:
        annotations_st = get_storage_create(
            "web-apps::annotations", parent_id=app["id"]
        )
        if annotations_st:
            key = f"scan-result:{source_id}"
            base_storage = (
                target_storage_name.split("::")[-1]
                if "::" in target_storage_name
                else target_storage_name
            )

            # The API also checks for base_storage as a fallback
            completed_annotations = annotations_st.get_filtered(
                f"key = '{key}' AND (storage_name = '{target_storage_name}' OR storage_name = '{base_storage}')"
            )
            if completed_annotations:
                results.append(
                    {
                        "info": "Scan completed with no results.",
                        "value": completed_annotations[0].get("value"),
                        "source_id": source_id,
                        "timestamp": completed_annotations[0].get("timestamp"),
                    }
                )

    if not results:
        return "No new scan results found yet."

    return f"Found {len(results)} entries/markers for source_id: {source_id}"


async def main():
    print(f"--- Triggering Local Scan for {APP_NAME} ---")

    # 1. Trigger the scan via local function (mimics API call to scan_app)
    result = await scan_app(APP_NAME, CONFIG_XML)
    print("Trigger Result:", result)

    if result.get("status") != "success":
        print("Failed to trigger scan")
        return

    source_id = result.get("source_id")

    # 2. Check if entries are ready (mimics ScheduledFunction.progress)
    print("\n--- Checking if entries are ready (Progress Logic) ---")
    ready = await check_entries_ready(APP_NAME, "py_mcp_ai_perform_scanning")

    # 3. Check for results (mimics check_results endpoint)
    print("\n--- Checking for results (API Logic) ---")
    results_status = await check_results_local(APP_NAME, source_id, "scanning")
    print("Results Status:", results_status)


if __name__ == "__main__":
    asyncio.run(main())
