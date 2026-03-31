from typing import Optional, Any, Union
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from rcn_core.mcp.api import create_mcp_router
from rcn_web.storage.utils import get_storage
from rcn_core.storage.bases import get_storage_create


def _resolve_storage(
    storage_name: str, parent_id: Optional[Union[int, str]] = None
) -> Any:
    st = get_storage()
    if not st:
        return None

    # If parent_id is provided, we can directly resolve via the global factory
    if parent_id is not None:
        return get_storage_create(storage_name, parent_id=parent_id)

    # If no parent_id, we rely on the storage object to decide context (e.g. default target)
    if hasattr(st, "get_storage_create"):
        try:
            return st.get_storage_create(storage_name)
        except (IndexError, AttributeError):
            # Fallback
            if hasattr(st, "targets") and st.targets:
                first_target = next(iter(st.targets.values()))
                return get_storage_create(storage_name, parent_id=first_target.id)
            return None

    return None


# Create router manually for testing and including standardized MCP routes
router = APIRouter(prefix="/mcp")


# Local implementations for backward compatibility endpoints
async def preview_storage(payload):
    from rcn_core.mcp.utils import render_storage_view

    collection = payload.get("collection") or payload.get("type")
    parent_id = payload.get("parent_id")
    sql_filter = payload.get("filter") or payload.get("sql_filter")

    storage = _resolve_storage(collection, parent_id)
    if not storage:
        return {"error": f"Collection '{collection}' not found"}

    return render_storage_view(storage, filter=sql_filter, is_preview=True)


async def view_storage(payload):
    from rcn_core.mcp.utils import render_storage_view

    collection = payload.get("collection") or payload.get("type")
    parent_id = payload.get("parent_id")
    sql_filter = payload.get("filter") or payload.get("sql_filter")
    page = payload.get("page", 1)
    limit = payload.get("limit", 20)

    storage = _resolve_storage(collection, parent_id)
    if not storage:
        return {"error": f"Collection '{collection}' not found"}

    return render_storage_view(
        storage, page=page, limit=limit, filter=sql_filter, is_preview=False
    )


async def execute_action(payload):
    # This is a placeholder that can be patched in tests
    # In production, it returns an error unless it's specifically patched or implemented.
    return {
        "status": "error",
        "message": "Generic action endpoint is deprecated. Use /mcp/action instead.",
    }


@router.post("/preview/generic")
async def preview_generic(req: Request):
    payload = await req.json()
    result = await preview_storage(payload)
    return JSONResponse(result)


@router.post("/view/generic")
async def view_generic(req: Request):
    payload = await req.json()
    result = await view_storage(payload)
    return JSONResponse(result)


@router.post("/action")
async def action_endpoint(req: Request):
    payload = await req.json()
    result = await execute_action(payload)
    return JSONResponse(result)


@router.post("/describe-target")
async def describe_target(req: Request):
    """Describe target and return storage preview information."""
    # Lazy imports to avoid circular dependencies
    from rcn_web.core.utils import get_storage
    from rcn_core.storage.bases import get_storage_create
    from rcn_web.core.utils import web_match_storage

    payload = await req.json()
    target_id = payload.get("target")
    # Retrieve the current target storage (ignoring target_id for now)
    target_storage = get_storage()
    if not target_storage:
        return JSONResponse({"error": "No target storage found"}, status_code=404)

    # Basic target metadata (fallback to None if attributes missing)
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
            if storage_name == "flows":
                # web_match_storage returns list of dicts with storage key
                matches = web_match_storage("flows")
                st = matches[0]["storage"] if matches else None
            else:
                st = get_storage_create(storage_name)
            if st is None:
                storage_previews[storage_name] = {"count": 0, "columns": []}
                continue
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


# Include standardized MCP routes from rcn-core (LAST to allow overrides)
mcp_router = create_mcp_router(storage_resolver=_resolve_storage, prefix="")
router.include_router(mcp_router)
