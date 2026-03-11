#! /usr/bin/env python3

import requests
from typing import Optional, List, Any
from fastmcp import FastMCP

# Initialize MCP
mcp = FastMCP("RCN Server Data Explorer (New Architecture)")

# Configuration
# This points to the RCN Web server running the new rcn_core.mcp router
RCN_SERVER_URL = "http://localhost:8023"

# --- Generic Helpers ---


def _call_action(action_name: str, params: dict):
    """
    Generic helper to call the unified /mcp/action endpoint.
    """
    payload = {"action": action_name, "params": params}
    try:
        resp = requests.post(f"{RCN_SERVER_URL}/mcp/action", json=payload)
        if resp.status_code != 200:
            return f"Error executing '{action_name}': {resp.text}"

        try:
            return resp.json()
        except:
            return resp.text

    except Exception as e:
        return f"Connection error: {e}"


# --- Tools ---


@mcp.tool
def preview_storage(
    storage_name: str, parent_id: Optional[str] = None, sql_filter: Optional[str] = None
) -> str:
    """
    Get a text preview of storages using the unified endpoint.
    """
    payload = {"collection": storage_name}
    if parent_id:
        payload["parent_id"] = parent_id
    if sql_filter:
        payload["filter"] = sql_filter

    try:
        resp = requests.post(f"{RCN_SERVER_URL}/mcp/preview", json=payload)
        if resp.status_code != 200:
            return f"Error fetching preview: {resp.text}"
        return resp.text
    except Exception as e:
        return f"Connection error: {e}"


@mcp.tool
def view_storage(
    storage_name: str,
    parent_id: Optional[str] = None,
    page: int = 1,
    limit: int = 1000,
    sql_filter: Optional[str] = None,
) -> str:
    """
    View entries in storages using the unified endpoint.
    """
    payload = {"collection": storage_name, "page": page, "limit": limit}
    if parent_id:
        payload["parent_id"] = parent_id
    if sql_filter:
        payload["filter"] = sql_filter
    
    try:
        resp = requests.post(f"{RCN_SERVER_URL}/mcp/view", json=payload, timeout=30.0)
        if resp.status_code != 200:
            return f"Error fetching view: {resp.text}"
        return resp.text
    except Exception as e:
        return f"Connection error: {e}"


@mcp.tool
def list_applications(
    targets: Optional[List[str]] = None,
    sql_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 1000,
) -> str:
    """
    List and filter applications (Specialized view for 'web-apps').
    """
    final_filter = sql_filter
    if targets:
        target_filters = [f"site LIKE '%{t}%'" for t in targets]
        combined_targets = " OR ".join(target_filters)
        if final_filter:
            final_filter = f"({final_filter}) AND ({combined_targets})"
        else:
            final_filter = combined_targets

    # Re-use the view_storage tool logic
    # Note: view_storage is a function tool, calling it directly works if it's a python function
    # but with @mcp.tool it might be wrapped.
    # FastMCP tools are callable as normal functions.
    return view_storage.fn(
        storage_name="web-apps", page=page, limit=limit, sql_filter=final_filter
    )


@mcp.tool
def add_note(
    app_name: str,
    entry_id: str,
    note_key: str,
    note_value: str,
    storage_name: Optional[str] = "web-apps::annotations",
):
    """
    Adds a note to an entry.
    Refactored to use the generic 'action' endpoint.
    """
    return _call_action(
        "add_note",
        {
            "app_name": app_name,
            "entry_id": entry_id,
            "note_key": note_key,
            "note_value": note_value,
            "storage_name": storage_name,
        },
    )


@mcp.tool
def create_yaml_scheduled_function(
    name: str,
    schedule: str,
    python_code: str,
    description: str = "",
    target_yaml: str = "basic_recon_flow.yaml",
    enabled: bool = True,
    run_now: bool = False,
):
    """
    Creates a scheduled function.

    IMPORTANT: The heavy lifting (file writing, YAML editing) has been moved to the Server
    as a registered action. This client just passes the parameters.
    """
    return _call_action(
        "create_scheduled_function",
        {
            "name": name,
            "schedule": schedule,
            "python_code": python_code,
            "description": description,
            "target_yaml": target_yaml,
            "enabled": enabled,
            "run_now": run_now,
        },
    )


@mcp.tool
def perform_scanning(app_name: str, config_xml: str) -> str:
    """
    Performs Nuclei scanning.
    Invokes the 'scan_app' action on the server.
    """
    return _call_action(
        "scan_app",
        {"app_name": app_name, "config_xml": config_xml, "scan_type": "scanning"},
    )


@mcp.tool
def perform_fuzzing(app_name: str, config_xml: str) -> str:
    """
    Performs FFUF fuzzing.
    Invokes the 'scan_app' action on the server.
    """
    return _call_action(
        "scan_app",
        {"app_name": app_name, "config_xml": config_xml, "scan_type": "fuzzing"},
    )


@mcp.tool
def perform_action(action: str, params: dict) -> Any:
    """
    Unified tool to perform generic actions on the RCN Server.
    Use this if a specific tool is not available for the action you want to perform.
    """
    return _call_action(action, params)


if __name__ == "__main__":
    mcp.run()
