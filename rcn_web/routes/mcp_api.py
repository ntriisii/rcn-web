import sys
import os
import importlib
from typing import Optional, Any, Union
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from rcn_core.mcp.registry import registry
from rcn_core.mcp.api import create_mcp_router


@registry.action("describe_target")
def describe_target_action():
    """Describe target and return storage preview information."""
    from rcn_web.core.utils import get_target_storage

    # Use core utility to get storage
    target_storage = get_target_storage()
    if not target_storage:
        return {"error": "No target storage found"}

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

    return {"target": target_info, "storages": storage_previews}


# Create router using the standardized MCP routes from rcn-core

# This automatically provides /view, /preview, /action, /tools, /prompts
router = create_mcp_router(storage_resolver=_resolve_storage, prefix="/mcp")
