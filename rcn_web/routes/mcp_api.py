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

    # 3. Try global storage resolution (Most direct fallback)
    target_storage = get_storage()
    if target_storage:
        try:
            if hasattr(target_storage, "targets") and target_storage.targets:
                # If parent_id provided, prioritize the target that matches it
                if pid:
                    pid_str = str(pid)
                    for tname, t in target_storage.targets.items():
                        if tname == "__multi_target__":
                            continue
                        if str(t.id) == pid_str:
                            # Use the specific target to create storage
                            st = t.get_storage_create(storage_name, parent_id=int(pid))
                            # Ensure the storage instance is actually scoped to this parent_id
                            # get_storage_create might return a cached instance with a different parent_id
                            if hasattr(st, "_parent_id"):
                                st._parent_id = int(pid)

                            # DEBUG
                            with open("/tmp/mcp_debug.log", "a") as f:
                                f.write(
                                    f"Resolved st: {st} with parent_id: {st.parent_id} for pid: {pid}\n"
                                )
                                f.write(f"Storage name: {st.storage_name}\n")
                                try:
                                    f.write(f"Count: {len(st)}\n")
                                except:
                                    f.write("Count failed\n")
                            return st

                for tname, t in target_storage.targets.items():
                    if tname == "__multi_target__":
                        continue
                    st = t.get_storage_create(storage_name)
                    if len(st) > 0:
                        return st
                for tname, t in target_storage.targets.items():
                    if tname != "__multi_target__":
                        return t.get_storage_create(storage_name)
            if hasattr(target_storage, "get_storage_create"):
                return target_storage.get_storage_create(storage_name, parent_id=pid)
        except Exception:
            pass

    # 2. Try project-specific matcher (Discovery / Fallback)
    from rcn_web.core.utils import web_match_storage

    matches = web_match_storage(storage_name)
    if matches:
        if pid is not None:
            for m in matches:
                st = m["storage"]
                # Convert to str for comparison to handle int/str mismatch
                if (hasattr(st, "parent_id") and str(st.parent_id) == str(pid)) or (
                    hasattr(st, "_parent_id") and str(st._parent_id) == str(pid)
                ):
                    return st
        return matches[0]["storage"]

    return None


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
