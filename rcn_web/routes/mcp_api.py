from typing import Optional, Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse

# Import placeholder functions for MCP actions
from rcn_core.mcp.api import preview_storage, view_storage, execute_action
from rcn_web.storage.utils import get_storage
from rcn_core.storage.bases import get_storage_create


def _resolve_storage(storage_name: str, parent_id: Optional[int | str] = None) -> Any:
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


# Create router manually for testing
router = APIRouter(prefix="/mcp")


@router.post("/preview/generic")
async def preview_generic(payload: dict):
    from rcn_core.mcp.api import preview_storage

    result = preview_storage(payload)
    return JSONResponse(result)


@router.post("/view/generic")
async def view_generic(payload: dict):
    from rcn_core.mcp.api import view_storage

    result = view_storage(payload)
    return JSONResponse(result)


@router.post("/action")
async def action_endpoint(payload: dict):
    from rcn_core.mcp.api import execute_action

    result = execute_action(payload)
    return JSONResponse(result)
