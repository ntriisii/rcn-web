from typing import Optional, Any, Union
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse

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

    # 2. Try global storage resolution first (Most direct)
    target_storage = get_storage()
    if target_storage:
        try:
            # If it's a MultiTargetStorage, ensure we pick a valid target
            if hasattr(target_storage, "targets") and target_storage.targets:
                # Try to match pid if provided
                if pid:
                    for t in target_storage.targets.values():
                        if str(t.id) == str(pid):
                            return t.get_storage_create(storage_name)

                # Search across all targets for one that has this collection with data
                for tname, t in target_storage.targets.items():
                    if tname == "__multi_target__":
                        continue
                    st = t.get_storage_create(storage_name)
                    # If it has data, this is likely the one we want
                    if len(st) > 0:
                        return st

                # Fallback to first non-metadata target
                for tname, t in target_storage.targets.items():
                    if tname != "__multi_target__":
                        return t.get_storage_create(storage_name)

            # Direct resolution if it's a single TargetStorage
            if hasattr(target_storage, "get_storage_create"):
                return target_storage.get_storage_create(storage_name, parent_id=pid)
        except Exception:
            pass

    # 3. Try project-specific matcher (Discovery / Fallback)
    matches = web_match_storage(storage_name)
    if matches:
        if pid is not None:
            for m in matches:
                st = m["storage"]
                if hasattr(st, "parent_id") and str(st.parent_id) == str(pid):
                    return st
        return matches[0]["storage"]

    # 4. Final Last Resort: Force load from current TARGET_DIR
    import rcn_core.globals
    from rcn_core.storage.target_storage import TargetStorage

    tdir = getattr(rcn_core.globals, "TARGET_DIR", None)
    if tdir and os.path.exists(tdir):
        try:
            ts = TargetStorage.load(os.path.basename(tdir.rstrip("/")), tdir)
            return ts.get_storage_create(storage_name)
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
