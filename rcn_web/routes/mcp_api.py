import sys
import os
import importlib
from typing import Optional, Any, Union
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse, PlainTextResponse

from rcn_core.mcp.registry import registry
from rcn_core.mcp.api import create_mcp_router


def _resolve_storage(
    storage_name: str, parent_id: Optional[Union[int, str]] = None
) -> Any:
    """Wrapper for storage resolution to allow easier mocking in tests."""
    return _resolve_storage_impl(storage_name, parent_id)


def _resolve_storage_impl(
    storage_name: str, parent_id: Optional[Union[int, str]] = None
) -> Any:
    from rcn_web.core.utils import (
        get_target_storage,
        RemoteFlowsAdapter,
        web_match_storage,
    )

    # Normalize parent_id
    pid = parent_id if parent_id and parent_id != 0 and parent_id != "0" else None

    # 1. Specialized flows handling
    if storage_name == "flows":
        return RemoteFlowsAdapter.get_instance()

    # 2. Resolve target context
    mts = get_target_storage()
    if not mts:
        return None

    # Default behavior: If no parent_id is provided, default to viewing the entire table.
    # We return a storage object with parent_id=None to disable hierarchical filtering.
    if pid is None:
        from rcn_core.storage.implementations import BasicDataStorage

        return BasicDataStorage(storage_name=storage_name, parent=mts, parent_id=None)

    # 3. Handle hierarchical storages (e.g. web-apps::app-flows)
    if "::" in storage_name:
        try:
            st_list = mts.get_storage_create(storage_name, parent_id=int(pid))
        except (ValueError, TypeError):
            st_list = mts.get_storage_create(storage_name, parent_id=pid)
        return st_list[0] if st_list else None

    # 4. Top-level resolution
    st_list = mts.get_storage_create(storage_name, parent_id=pid)
    return st_list[0] if st_list else None


@registry.action("describe_target")
async def describe_target_action():
    """Describe target and return storage preview information."""
    from rcn_web.core.utils import get_target_storage

    # Use core utility to get storage
    target_storage = get_target_storage()
    if not target_storage:
        return "Error: No target storage found"

    # Basic target metadata
    target_id = getattr(target_storage, "id", None)
    target_site = getattr(target_storage, "site", None)

    output = f"Target ID: {target_id}\n"
    output += f"Target Site: {target_site}\n"
    output += "\nStorages:\n"

    # Query all storages from the database tables
    storages_to_preview = []
    try:
        from rcn_core.storage.connections import get_db_connection

        db_path = target_storage.target_directory / "rcn_automation_data.db"
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            for row in cursor.fetchall():
                table_name = row["name"]
                if table_name in [
                    "sqlite_sequence",
                    "delayed_operations",
                    "automation_metadata",
                    "targets",
                ]:
                    continue
                storages_to_preview.append(table_name)
    except Exception as e:
        output += f"Warning: Could not list all storages ({str(e)})\n"
        # Fallback to a basic list if DB query fails
        storages_to_preview = ["web-apps", "flows"]

    if "flows" not in storages_to_preview:
        storages_to_preview.append("flows")

    for storage_name in storages_to_preview:
        try:
            st = _resolve_storage(storage_name)
            if st is None:
                continue

            # Use storage methods for consistent data retrieval
            count = 0
            try:
                # Use storage_length() if available (total physical entries)
                # otherwise fallback to scoped len(st)
                if hasattr(st, "storage_length"):
                    count = st.storage_length()
                    # print(f"DEBUG: {storage_name} storage_length={count}")
                else:
                    count = len(st)
            except (TypeError, AttributeError):
                # Fallback for adapters that don't support len()
                try:
                    entries = st.get()
                    count = len(entries)
                except:
                    pass

            entries = st.get()
            columns = list(entries[0].keys()) if entries else []

            output += f" - {storage_name}: {count} entries"
            if columns:
                output += f" (columns: {', '.join(columns[:10])}{'...' if len(columns) > 10 else ''})"
            output += "\n"

        except Exception as e:
            output += f" - {storage_name}: Error ({str(e)})\n"

    return PlainTextResponse(output)


# Create router using the standardized MCP routes from rcn-core

# This automatically provides /view, /preview, /action, /tools, /prompts
router = create_mcp_router(storage_resolver=_resolve_storage, prefix="/mcp")


@router.post("/describe-target")
async def describe_target_endpoint(req: Request):
    from rcn_web.core.utils import get_target_storage

    target_storage = get_target_storage()
    if not target_storage:
        return JSONResponse({"error": "No target storage found"}, status_code=404)

    storages_to_check = ["web-apps", "flows", "web-apps::app-links"]
    storages_results = {}

    for name in storages_to_check:
        st = _resolve_storage(name)
        if st is not None:
            try:
                count = len(st)
            except:
                try:
                    count = len(st.get())
                except:
                    count = 0

            try:
                entries = st.get()
                columns = list(entries[0].keys()) if entries else []
            except:
                columns = []

            storages_results[name] = {"count": count, "columns": columns}
        else:
            storages_results[name] = {"count": 0, "columns": []}

    return JSONResponse(
        {
            "target": {
                "id": getattr(target_storage, "id", None),
                "site": getattr(target_storage, "site", None),
            },
            "storages": storages_results,
        }
    )
