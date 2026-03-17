#! /home/ahmed/programming-projects/python/rcn-web/.venv/bin/python3

import sys
import yaml
import json
import requests

from typing import Optional, List
from fastmcp import FastMCP
from pentest_utils.web.mcp_utils import get_flow as utils_get_flow


# Initialize MCP
mcp = FastMCP("RCN Server Data Explorer (HTTP)")

# Configuration
RCN_SERVER_URL = "http://localhost:8023"


# --- Tools ---
@mcp.tool
def preview_storage(
    storage_name: str, app_id: Optional[int] = None, sql_filter: Optional[str] = None
) -> str:
    """
    Get a text preview of storages.

    Args:
        storage_name: Storage name to preview (e.g. 'found-ips', 'js-links', 'web-apps').
        app_id: Optional. Application ID. If provided, looks for storage within this application.
        sql_filter: Optional. SQL filter to apply to storage entries (e.g. "url LIKE '%login%'").
    """
    payload = {"type": storage_name}
    if app_id:
        payload["parent_id"] = app_id
    if sql_filter:
        payload["sql_filter"] = sql_filter
    print(f"Preview storage payload: {payload}")

    try:
        resp = requests.post(f"{RCN_SERVER_URL}/mcp/preview/generic", json=payload)
        if resp.status_code != 200:
            return f"Error fetching preview: {resp.text}"

        try:
            return resp.json()
        except:
            return resp.text

    except Exception as e:
        return f"Connection error: {e}"


@mcp.tool
def view_storage(
    storage_name: str,
    app_id: Optional[int] = None,
    page: int = 1,
    limit: int = 1000,
    sql_filter: Optional[str] = None,
) -> str:
    """
    View entries in storages (paginated text table).

    Args:
        storage_name: Storage name.
        app_id: Optional. Application ID.
        page: Page number (starts at 1).
        limit: Number of entries per page.
        sql_filter: Optional. SQL filter to apply to storage entries (e.g. "url LIKE '%login%'").
    """
    payload = {"type": storage_name, "page": page, "limit": limit}

    if app_id:
        payload["parent_id"] = app_id
    if sql_filter:
        payload["sql_filter"] = sql_filter

    try:
        resp = requests.post(
            f"{RCN_SERVER_URL}/mcp/view/generic", json=payload, timeout=30.0
        )
        if resp.status_code != 200:
            return f"Error fetching view: {resp.text}"

        try:
            return resp.json()
        except:
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
    List and filter applications.

    Args:
        targets: Optional. List of target site names to search for (e.g., ['example.com']).
        sql_filter: Optional. SQL filter to apply to applications (e.g. "status_code = 200 AND technologies LIKE '%React%'").
        page: Page number (starts at 1).
        limit: Number of applications per page.
    """
    final_filter = sql_filter
    if targets:
        target_filters = [f"site LIKE '%{t}%'" for t in targets]
        combined_targets = " OR ".join(target_filters)
        if final_filter:
            final_filter = f"({final_filter}) AND ({combined_targets})"
        else:
            final_filter = combined_targets

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
    category: str = "notes",
):
    """
    Adds a note to entries via the server API.

    Args:
        app_name: Application name.
        entry_id: The ID of the entry (omit or pass random value if the note is destined for application).
        note_key: Note tag/key.
        note_value: Note content.
        storage_name: Storage name (default is "web-apps::annotations" for application itself).
        category: Note category (default is "notes").
    """

    payload = {
        "app_name": [app_name],
        "storage_name": [storage_name] if storage_name else [],
        "entry_id": entry_id,
        "key": note_key,
        "value": note_value,
        "category": category,
    }

    try:
        resp = requests.post(
            f"{RCN_SERVER_URL}/storage/addEntryAnnotation", json=payload
        )
        if resp.status_code != 200:
            return f"Error adding note: {resp.text}"

        return f"Note added: {resp.json()}"

    except Exception as e:
        return f"Connection error: {e}"


@mcp.tool
def delegate_to_acp(
    app_name: str,
    agent_name: str,
    instructions: str,
    storage_name: str,
    entries_ids: Optional[str] = None,
) -> str:
    """
    Delegates a task to an ACP agent (e.g., 'gemini-3-flash').

    Args:
        app_name: Application name.
        agent_name: Name of the agent to handle the task.
        instructions: What the agent should do.
        storage_name: The storage name where entries come from.
        entries_ids: Optional. Comma-separated list of entry IDs to process.
    """
    payload = {
        "action": "delegate_to_acp",
        "params": {
            "app_name": app_name,
            "agent_name": agent_name,
            "instructions": instructions,
            "storage_name": storage_name,
            "entries_ids": entries_ids,
        },
    }

    try:
        resp = requests.post(f"{RCN_SERVER_URL}/mcp/action", json=payload)
        if resp.status_code != 200:
            return f"Error delegating task: {resp.text}"
        return f"Task delegated successfully: {resp.json()}"
    except Exception as e:
        return f"Connection error: {e}"


@mcp.tool
def create_yaml_scheduled_function(
    name: str,
    schedule: str,
    python_code: str,
    description: str = "",
    python_fn: Optional[str] = None,
    python_filename: Optional[str] = None,
    target_yaml: str = "basic_recon_flow.yaml",
    enabled: bool = True,
    run_now: bool = False,
):
    """
    Creates or updates a scheduled function in a YAML file and saves the corresponding Python code.
    Optionally executes the function immediately.

    This tool can create two types of scheduled functions:
    1. Storage-based: Iterates over new/unscanned entries in a storage (e.g., applications, links).
       It uses the `get_unscanned_entries` helper.
    2. Non-storage-based: Runs general logic without being tied to a specific storage.

    **Example 1: Storage-based function (e.g., process new web links)**
    ```python
    # python_code = '''
    from rcn_server.rcn_helpers.scanning.utils import get_unscanned_entries

    async def process_new_links(event, scheduled_md):
        # event['name'] will be 'my_link_processor'
        async with get_unscanned_entries(event['name'], event) as unscanned:
            if not unscanned:
                return
            for item_id, item_data in unscanned.items():
                link = item_data['entry']
                print(f"Processing new link: {link['url']}")
    # '''
    ```

    **Example 2: Non-storage-based function (e.g., run a daily cleanup)**
    ```python
    # python_code = '''
    async def daily_cleanup(event, scheduled_md):
        print("Running daily cleanup task!")
        # Add custom logic here
    # '''
    ```

    The tool will create the python file in `rcn_server/rcn_helpers/automation/`. The `python_fn` in the YAML will be automatically set to `py_<python_filename_without_extension>`.

    Args:
        name: Unique name for the event. This is used for tracking scanned items.
        schedule: Schedule string (e.g., '10m', '1h', '1d').
        python_code: The complete Python code for the scheduled function.
        description: A short description of what the function does.
        python_fn: Overrides the function name in the YAML. If omitted, it's derived from `python_filename`.
        python_filename: The name of the file to save the python code (e.g., 'my_task.py'). If omitted, a name is generated from the event name.
        target_yaml: Path to the YAML file to edit (default: 'basic_recon_flow.yaml').
        enabled: Whether the task is enabled by default.
        run_now: If True, executes the function immediately after creating/updating it.
    """

    import os
    import inspect
    from ruamel.yaml import YAML
    from pathlib import Path

    messages = []

    # Handle Python File Creation
    if not python_filename:
        python_filename = name.replace("-", "_") + ".py"

    target_dir = Path(os.getcwd())

    file_path = target_dir / python_filename

    try:
        file_exists = file_path.exists()
        with open(file_path, "a") as f:
            if file_exists:
                f.write("\n\n")
            f.write(python_code)

        if file_exists:
            messages.append(f"Function appended to existing file '{python_filename}'.")
        else:
            messages.append(
                f"File '{python_filename}' created successfully with the function."
            )
    except Exception as e:
        return f"Error writing Python file: {e}"

    # Determine the function name for the YAML
    if not python_fn:
        fn_name_base = Path(python_filename).stem
        python_fn = f"py_{fn_name_base}"

    yaml_path = Path(target_yaml)
    if not yaml_path.is_absolute():
        yaml_path = Path(os.getcwd()) / target_yaml

    yaml_obj = YAML()
    yaml_obj.preserve_quotes = True

    try:
        if yaml_path.exists():
            with open(yaml_path, "r") as f:
                data = yaml_obj.load(f) or {}
        else:
            data = {}
            messages.append(f"Creating new YAML file: '{yaml_path}'")

        if "time-events" not in data:
            data["time-events"] = []

        events = data["time-events"]
        existing_event = next((e for e in events if e.get("name") == name), None)

        new_event = {
            "name": name,
            "every": schedule,
            "enabled": enabled,
            "description": description,
            "function": python_fn,
        }

        if existing_event:
            existing_event.update(new_event)
            action = "updated"

        else:
            events.append(new_event)
            action = "created"

        with open(yaml_path, "w") as f:
            yaml_obj.dump(data, f)

        messages.append(f"Scheduled function '{name}' {action} in '{yaml_path}'.")

    except Exception as e:
        return f"Error modifying YAML: {e}"

    if run_now:
        # Deduce function name
        fn_name = python_fn
        if fn_name.startswith("py_"):
            fn_name = fn_name[3:]

        # Append execution code
        exec_code = f"""
{python_code}

import inspect

async def main():
    try:
        fn_name = '{fn_name}'
        fn = locals().get(fn_name) or globals().get(fn_name)
        
        if fn and callable(fn):
            sig = inspect.signature(fn)
            # Check if it looks like (event, scheduled_md)
            kwargs = {{}}
            if len(sig.parameters) >= 2:
                kwargs = {{'event': {{'name': '{name}'}}, 'scheduled_md': {{}}}}
                
            if inspect.iscoroutinefunction(fn):
                await fn(**kwargs)
            else:
                fn(**kwargs)
            return f"Executed {{fn_name}}"
    except Exception as e:
        return f"Execution error: {{e}}"
"""
        try:
            resp = requests.post(
                f"{RCN_SERVER_URL}/mcp/run_script", json={"code": exec_code}
            )
            if resp.status_code == 200:
                messages.append("Function executed immediately.")
            else:
                messages.append(f"Immediate execution failed: {resp.text}")
        except Exception as e:
            messages.append(f"Immediate execution error: {e}")

    return "\n".join(messages)


def _perform_security_task(app_name: str, scan_type: str, config_xml: str) -> str:
    import time
    import random
    import string

    # Generate unique source ID
    rand_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    source_id = f"mcp-{scan_type}-{rand_str}"

    # Wrap config XML
    wrapped_xml = f"<root><source_id>{source_id}</source_id>{config_xml}</root>"

    start_ts = time.time()

    note_key = f"tool-{scan_type}"
    results = []

    # We collect all added notes to process them
    all_added_notes = []

    # Simplified: Handle single app
    app = app_name

    payload = {
        "app_name": [app],
        "storage_name": ["web-apps"],
        "entry_id": app,
        "key": note_key,
        "value": wrapped_xml,
    }

    try:
        resp = requests.post(
            f"{RCN_SERVER_URL}/storage/addEntryAnnotation", json=payload
        )
        if resp.status_code != 200:
            results.append(f"Error adding note for {app}: {resp.text}")
        else:
            resp_data = resp.json()
            if isinstance(resp_data, dict) and "annotations" in resp_data:
                all_added_notes.extend(resp_data["annotations"])
                results.append(
                    f"Scheduled {scan_type} for {app} (Source ID: {source_id})"
                )

            elif isinstance(resp_data, dict) and "notes" in resp_data:
                all_added_notes.extend(resp_data["notes"])
                results.append(
                    f"Scheduled {scan_type} for {app} (Source ID: {source_id})"
                )

            else:
                results.append(
                    f"Scheduled {scan_type} for {app} (Response: {resp_data})"
                )

    except Exception as e: results.append(f"Connection error for {app}: {e}")

    if all_added_notes:
        results.append("Waiting for results (polling storage)...")

        import json

        # Poll for results
        max_retries = 180  # 15 minutes
        found_any = False

        for _ in range(max_retries):
            time.sleep(5)

            # Check for the single app
            resp = requests.post(
                f"{RCN_SERVER_URL}/mcp/check_scan_results",
                json={
                    "app_site": app,
                    "source_name": source_id,
                    "min_timestamp": start_ts,
                    "scan_type": scan_type,
                },
            )
            if resp.status_code == 200:
                resp_text = resp.text
                if "No new scan results found yet." not in resp_text:
                    found_any = True
                    results.append(resp_text)
                    break

        if not found_any:
            results.append("No results found within timeout.")

    return "\n".join(results)


@mcp.tool
def perform_scanning(app_name: str, config_xml: str) -> str:
    """
    Performs Nuclei security scanning on specified applications using the provided XML configuration.
    Waits for the scan to finish and returns the results.

    Args:
        app_name: Application name (site name) to scan.
        config_xml: The XML configuration for the scan (e.g., <scanning>...</scanning>).
    """
    return _perform_security_task(app_name, "scanning", config_xml)


@mcp.tool
def perform_fuzzing(app_name: str, config_xml: str) -> str:
    """
    Performs FFUF fuzzing on specified applications using the provided XML configuration.
    Waits for the fuzzing to finish and returns the results.

    Args:
        app_name: Application name (site name) to fuzz.
        config_xml: The XML configuration for the fuzz (e.g., <fuzzing>...</fuzzing>).
    """
    return _perform_security_task(app_name, "fuzzing", config_xml)


RCN_SERVER_URL = "http://localhost:8023"
if __name__ == "__main__": mcp.run()
