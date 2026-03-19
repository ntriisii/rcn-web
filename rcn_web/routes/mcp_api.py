from typing import Optional, Any
from fastapi import APIRouter
from rcn_core.mcp.api import create_mcp_router
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


# Create the standardized router
router = create_mcp_router(
    storage_resolver=_resolve_storage, prefix="/mcp", tags=["mcp"]
)

# We can add custom endpoints to this router if needed,
# e.g. check_scan_results if it's not covered by actions or generic view.
# But for now, we try to stick to the standard.

# Note: check_scan_results was a specific endpoint in the old API.
# We might need to keep it if the client relies on it for polling.
# But the "new mindset" implies using `scan_app` action which returns immediately,
# and maybe the client should POLL the view instead of a custom endpoint?
# Or we can just re-add it here.

from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel


class ScanResultsRequest(BaseModel):
    app_site: Optional[str] = None
    app_id: Optional[str | int] = None
    source_name: str
    min_timestamp: float
    scan_type: str


@router.post("/check_scan_results")
async def check_scan_results(request: ScanResultsRequest):
    from rcn_web.core.utils import get_app_by_id, get_app_by_site

    st = get_storage()
    app = None
    if request.app_id:
        app = get_app_by_id(st, request.app_id)
    if not app and request.app_site:
        app = get_app_by_site(st, request.app_site)

    if not app:
        return JSONResponse({"status": "error", "message": "App not found"})

    results = []

    target_storage_name = None
    if request.scan_type == "scanning":
        target_storage_name = "web-apps::nuclei-scanning"
    elif request.scan_type == "fuzzing":
        target_storage_name = "web-apps::fuzzing-data"
    else:
        return JSONResponse(
            {
                "status": "error",
                "message": "Invalid scan_type. Must be 'scanning' or 'fuzzing'.",
            },
            status_code=404,
        )

    # 1. Check for finished annotation first
    annotations_st = get_storage_create("web-apps::annotations", parent_id=app["id"])
    key = f"scan-result:{request.source_name}"

    # Check if the scan is marked as finished
    completed = annotations_st.get_filtered(f"key = '{key}' AND value = 'finished'")

    if not completed:
        return PlainTextResponse("No new scan results found yet.", status_code=404)

    # 2. If finished, fetch results from target storage
    st_obj = get_storage_create(target_storage_name, parent_id=app["id"])
    if st_obj:
        sid = st_obj.resolve_source_id(request.source_name)
        if sid:
            results = st_obj.get_filtered(
                f"source_id = {sid} AND timestamp >= {request.min_timestamp}"
            )

    # 3. If no entries, return empty response
    if not results:
        return PlainTextResponse("")

    # Format results as text
    if not results:
        return PlainTextResponse("No new scan results found yet.", status_code=404)

    text_output = []
    text_output.append(
        f"Scan Results for {request.source_name} (Type: {request.scan_type})"
    )
    text_output.append(f"Found {len(results)} entries.")
    text_output.append("")

    if results:
        # Determine keys from the first entry
        keys = list(results[0].keys())

        # Filter out internal keys if desired, similar to get_text_view
        internal_keys = ["source_id"]
        keys = [k for k in keys if k not in internal_keys]

        text_output.append("each line of entry in this storage consists of:")
        for k in keys:
            text_output.append(k)
        text_output.append("-------")
        text_output.append("and it will be seperated by ##")
        text_output.append("")
        text_output.append("DATA:")

        entry_blocks = []
        for row in results:
            entry_lines = []
            for k in keys:
                val = str(row.get(k, "")).replace("\n", " ")
                entry_lines.append(val)
            entry_blocks.append("\n".join(entry_lines))

        text_output.append("\n##\n".join(entry_blocks))

    return PlainTextResponse("\n".join(text_output))
