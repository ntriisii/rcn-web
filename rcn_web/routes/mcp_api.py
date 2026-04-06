from typing import Optional, Any, Union
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from rcn_core.mcp.api import create_mcp_router
from rcn_web.core.utils import get_storage, web_match_storage


def _resolve_storage(
    storage_name: str, parent_id: Optional[Union[int, str]] = None
) -> Any:
    # 1. Specialized flows handling
    if storage_name == "flows":
        from rcn_web.core.utils import RemoteFlowsAdapter

        return RemoteFlowsAdapter.get_instance()

    # 2. For sub-storages with a parent_id, resolve directly to ensure correct scoping
    if "::" in storage_name and parent_id:
        try:
            from rcn_core.storage.bases import get_storage_create as gsc

            return gsc(storage_name, parent_id=int(parent_id))
        except (ValueError, TypeError, Exception):
            pass

    # 3. Try project-specific matcher (handles 'web-apps', etc.)
    matches = web_match_storage(storage_name)
    if matches:
        # If parent_id is provided, try to find the specific app context among matches
        if parent_id is not None:
            for m in matches:
                st = m["storage"]
                if hasattr(st, "parent_id") and str(st.parent_id) == str(parent_id):
                    return st
        return matches[0]["storage"]

    # 4. Global storage fallback (handles MultiTargetStorage context)
    target_storage = get_storage()
    if target_storage:
        try:
            return target_storage.get_storage_create(storage_name, parent_id=parent_id)
        except Exception:
            pass

    return None


# Create router using the standardized MCP routes from rcn-core
# This automatically provides /view, /preview, /action, /tools, /prompts
router = create_mcp_router(storage_resolver=_resolve_storage, prefix="/mcp")


@router.post("/describe-target")
async def describe_target(req: Request):
    """Describe target and return storage preview information."""
    payload = await req.json()

    # Use core utility to get storage
    target_storage = get_storage()
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
