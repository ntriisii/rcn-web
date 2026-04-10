from rcn_core.mcp import register_action
from rcn_web.storage.utils import get_storage, get_app_by_site
from rcn_core.storage.bases import get_storage_create, add_annotation
from rcn_web.core.utils import get_root_storage
import asyncio
from fastapi.responses import JSONResponse
from typing import Optional, List

# rcn_core.mcp.core_actions provides create_scheduled_function


@register_action
async def run_script(code: str):
    """
    Executes a Python script in the server context.
    """
    import rcn_core.parse_yaml as pyaml
    from rcn_web.storage.utils import storage

    try:
        g = vars(pyaml).copy()
        if "storage" not in g:
            g["storage"] = storage
        l = {}
        exec(code, g, l)
        if "main" in l and asyncio.iscoroutinefunction(l["main"]):
            res = await l["main"]()
            return str(res) if res is not None else "Async execution completed."
        return "Script executed successfully."
    except Exception as e:
        return f"Error executing script: {e}"


@register_action
async def add_note(
    app_name: str,
    entry_id: str,
    note_key: str,
    note_value: str,
    storage_name: str = "web-apps::annotations",
    category: str = "notes",
):
    """
    Adds an annotation/note to an entry.
    """
    st = get_root_storage()
    if not st:
        return JSONResponse(
            {"status": "error", "message": "Storage not initialized"}, 500
        )

    parent_id = None
    if app_name:
        app = get_app_by_site(st, app_name)
        if app:
            parent_id = app["id"]

    # If parent_id not found but app_name provided, maybe it's the target name?
    # For now assume context resolution handles it or parent_id=None implies root.

    try:
        # Use the global add_annotation which resolves storage
        # We need to map key to category-key if needed, but add_annotation handles "-"

        # Note: add_annotation(entry_id, storage_name, key, value, parent_id, ...)
        # storage_name here is the target storage of the entry (e.g. web-apps::app-links)

        res_id = add_annotation(
            entry_id=entry_id,
            storage_name=storage_name,
            key=note_key,
            value=note_value,
            parent_id=parent_id,
            category=category,
        )
        return {"status": "success", "message": f"Note added with ID {res_id}"}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, 500)


@register_action
async def delegate_to_acp(
    app_name: str,
    agent_name: str,
    instructions: str,
    storage_name: str,
    entries_ids: Optional[str] = None,
):
    """
    Delegates a task to an ACP agent.
    """
    xml_value = f"<instructions>{instructions}</instructions>"
    if entries_ids:
        xml_value += f"<entries_ids>{entries_ids}</entries_ids>"
    if storage_name:
        xml_value += f"<storage>{storage_name}</storage>"

    # We add the note to the app itself
    return await add_note(
        app_name=app_name,
        entry_id=app_name,
        note_key=agent_name,
        note_value=xml_value,
        storage_name="targets::annotations",
        category="acp-agent-do",
    )


@register_action
async def scan_app(app_name: str, config_xml: str, **kwargs):
    """
    Triggers a Nuclei scanning task.
    """
    
    return await _trigger_security_task(app_name, config_xml, "scanning")


@register_action
async def fuzz_app(app_name: str, config_xml: str, **kwargs):
    """
    Triggers a FFUF fuzzing task.
    """
    
    return await _trigger_security_task(app_name, config_xml, "fuzzing")


async def _trigger_security_task(app_name: str, config_xml: str, scan_type: str):
    
    import random
    import string
    from rcn_web.storage.utils import get_storage, get_app_by_site
    from rcn_core.storage.bases import add_annotation
    from rcn_web.core.utils import get_root_storage

    st = get_root_storage()
    if not st: return {"status": "error", "message": "Storage not initialized"}
    
    app = get_app_by_site(st, app_name)
    if not app: return {"status": "error", "message": f"App {app_name} not found"}
    
    # Generate unique source ID
    rand_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    source_id = f"mcp-{scan_type}-{rand_str}"
    
    # Wrap config XML
    wrapped_xml = f"<root><source_id>{source_id}</source_id>{config_xml}</root>"
    category = f"tool-{scan_type}"
    
    try:
        # We add the annotation to the application
        res_id = add_annotation(
            entry_id=app["id"],
            storage_name="web-apps",
            key=source_id,
            value=wrapped_xml,
            parent_id=app["id"],
            category=category,
        )
        
        return {
            "status": "success",
            "source_id": source_id,
            "message": f"{scan_type.capitalize()} task started for {app_name}.",
        }
    
    except Exception as e: return {"status": "error", "message": str(e)}
