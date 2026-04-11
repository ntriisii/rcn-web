import sys
import os
import importlib
from typing import Optional, Any, Union
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse

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

    # 3. Handle hierarchical storages (e.g. web-apps::app-flows)
    if "::" in storage_name:
        if pid:
            try:
                st_list = mts.get_storage_create(storage_name, parent_id=int(pid))
            except (ValueError, TypeError):
                st_list = mts.get_storage_create(storage_name, parent_id=pid)
            return st_list[0] if st_list else None
        st_list = mts.get_storage_create(storage_name)
        return st_list[0] if st_list else None

    # 4. Top-level resolution
    st_list = mts.get_storage_create(storage_name)
    return st_list[0] if st_list else None


# Create router using the standardized MCP routes from rcn-core
# This automatically provides /view, /preview, /action, /tools, /prompts
router = create_mcp_router(storage_resolver=_resolve_storage, prefix="/mcp")


@router.get("/test-resolve")
def test_resolve():
    st = _resolve_storage("web-apps::app-flows")
    return {"found": st is not None, "repr": str(st)}


@router.post("/describe-target")
async def describe_target(req: Request):
    """Describe target and return storage preview information."""
    from rcn_web.core.utils import get_target_storage

    try:
        payload = await req.json()
    except Exception:
        payload = {}

    # Use core utility to get storage
    target_storage = get_target_storage()
    if not target_storage:
        return JSONResponse({"error": "No target storage found"}, status_code=404)

    # Basic target metadata
    target_info = {
        "id": getattr(target_storage, "id", None),
        "site": getattr(target_storage, "site", None),
    }

    storages_to_preview = [
        "web-apps",
        "web-apps::app-links",
        "web-apps::js-flows",
        "web-apps::annotations",
        "flows",
    ]

    storage_previews = {}
    for storage_name in storages_to_preview:
        try:
            st = _resolve_storage(storage_name)
            if st is None:
                storage_previews[storage_name] = {"count": 0, "columns": []}
                continue

            # Use storage methods for consistent data retrieval
            count = len(st)
            entries = st.get()
            columns = list(entries[0].keys()) if entries else []
            storage_previews[storage_name] = {"count": count, "columns": columns}
        except Exception as e:
            storage_previews[storage_name] = {
                "count": 0,
                "columns": [],
                "error": str(e),
            }

    result = {"target": target_info, "storages": storage_previews}
    return JSONResponse(result)
