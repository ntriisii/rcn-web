import sys
import os
import importlib
from typing import Optional, Any, Union
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse

# Force local rcn-core usage
core_path = os.path.expanduser("~/programming-projects/python/rcn-core/")
if core_path not in sys.path:
    sys.path.insert(0, core_path)

# Ensure latest core logic is used
for mod_name in ["rcn_core.data_access", "rcn_core.mcp.api", "rcn_core.storage.bases"]:
    if mod_name in sys.modules:
        importlib.reload(sys.modules[mod_name])

from rcn_core.mcp.api import create_mcp_router
from rcn_web.core.utils import get_storage, web_match_storage


def _resolve_storage(
    storage_name: str, parent_id: Optional[Union[int, str]] = None
) -> Any:
    # Normalize parent_id
    pid = parent_id if parent_id and parent_id != 0 and parent_id != "0" else None

    # 1. Specialized flows handling
    if storage_name == "flows":
        from rcn_web.core.utils import RemoteFlowsAdapter
        return RemoteFlowsAdapter.get_instance()

    # 2. Resolve target context
    target_storage = get_storage()
    if not target_storage:
        return None

    active_target = target_storage
    is_target_match = False

    if hasattr(target_storage, "targets") and target_storage.targets:
        # Find the specific target if pid matches a Target ID
        if pid:
            pid_str = str(pid)
            for tname, t in target_storage.targets.items():
                if tname == "__multi_target__":
                    continue
                if str(t.id) == pid_str:
                    active_target = t
                    is_target_match = True
                    break

        # Default to first real target if no match or no pid
        if not is_target_match:
            for tname, t in target_storage.targets.items():
                if tname != "__multi_target__":
                    active_target = t
                    break

    # 3. Handle hierarchical storages (e.g. web-apps::app-flows)
    if "::" in storage_name:
        # If no pid provided, or pid was a Target ID, we want an unscoped global view
        if pid is None or is_target_match:
            try:
                st = active_target.get_storage_create(storage_name)
                # Disable the parent_id filter so we see data across all sub-entities
                st._parent_id = None
                if "length" in st.__dict__:
                    del st.__dict__["length"]
                return st
            except Exception:
                pass

        # If pid is provided and wasn't a Target ID, it's likely a sub-entity ID (e.g. App ID)
        if pid:
            try:
                return active_target.get_storage_create(storage_name, parent_id=int(pid))
            except (ValueError, TypeError):
                return active_target.get_storage_create(storage_name, parent_id=pid)

    # 4. Handle top-level collections (e.g. web-apps)
    # If pid was a Target ID, use it. If not, don't use it for web-apps (it might be an app ID)
    if storage_name in ["web-apps", "all-web-apps", "apps"]:
        if is_target_match:
            return active_target.get_storage_create(storage_name, parent_id=pid)
        else:
            return active_target.get_storage_create(storage_name)

    # 5. Top-level resolution fallback
    return active_target.get_storage_create(storage_name, parent_id=pid)



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
