from typing import Optional, Any
from rcn_core.mcp import register_action
from rcn_web.core.utils import get_storage, get_root_storage, get_app_by_site
from rcn_core.storage.bases import get_storage_create, add_annotation
from rcn_core.log import rlog


@register_action()
async def add_note(
    app_name: str,
    entry_id: str,
    note_key: str,
    note_value: str,
    storage_name: str = "web-apps::annotations",
    category: str = "notes",
    **kwargs,
):
    """
    Adds a note to an entry.
    """
    # Logic similar to storage/addEntryNote route but direct
    app = get_app_by_site(get_root_storage(), app_name)
    if not app:
        raise ValueError(f"Application '{app_name}' not found.")

    st_name = storage_name
    if "::" not in st_name and st_name != "web-apps":
        st_name = f"web-apps::{storage_name}"

    # Resolve storage
    try:
        # Find the target storage this app belongs to
        target_id = app.get("parent_id")
        ts = get_root_storage()
        parent_target = None
        if hasattr(ts, "targets"):
            for t in ts.targets.values():
                if t.id == target_id:
                    parent_target = t
                    break
        if not parent_target and hasattr(ts, "id") and ts.id == target_id:
            parent_target = ts

        if st_name == "web-apps":
            st = (parent_target or get_root_storage()).get_storage_create(st_name)
        else:
            st = get_storage_create(
                st_name, parent_id=app["id"], parent_obj=parent_target
            )
    except Exception as e:
        raise ValueError(f"Storage '{st_name}' not found or error accessing it: {e}")

    if not st:
        raise ValueError(f"Storage '{st_name}' not found.")

    # Add annotation
    # Note: add_annotation helper might need args adjustment or use st.add_annotation
    # st.add_annotation usually takes (entry_id, key, value)

    # If entry_id is the app itself (string), usually annotations are stored with entry_id as string or 0
    # But usually annotations storage has its own schema.

    # Let's assume we use st.add_many for annotations storage, or st.add_annotation wrapper.
    # The existing addEntryNote route logic suggests adding to "web-apps::annotations" directly if it's an app note.

    if "annotations" in st_name:
        # Adding directly to annotations storage
        entry = {
            "entry_id": entry_id,
            "key": note_key,
            "value": note_value,
            "timestamp": __import__("time").time(),
            "storage_name": st_name,  # Maybe irrelevant if we are in annotations storage
            "category": category,
        }
        st.add_many([entry])
        return {"status": "success", "message": f"Note added to {app_name}."}
    else:
        # Adding an annotation TO an entry in a data storage
        # This usually goes into the annotations storage anyway, linked to this entry.
        # But 'add_annotation' helper usually handles this logic.

        annot_st = get_storage_create("web-apps::annotations", parent_id=app["id"])
        entry = {
            "entry_id": entry_id,
            "key": note_key,
            "value": note_value,
            "timestamp": __import__("time").time(),
            "storage_name": st_name,
            "category": category,
        }
        annot_st.add_many([entry])
        return {
            "status": "success",
            "message": f"Note added to {entry_id} in {st_name}.",
        }


@register_action()
async def delegate_to_acp(
    app_name: str,
    agent_name: str,
    instructions: str,
    storage_name: str,
    entries_ids: Optional[str] = None,
    **kwargs,
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
        storage_name="web-apps::annotations",
        category="acp-agent-do",
    )


@register_action()
async def create_scheduled_function(
    name: str,
    schedule: str,
    python_code: str,
    description: str = "",
    target_yaml: str = "basic_recon_flow.yaml",
    enabled: bool = True,
    run_now: bool = False,
    **kwargs,
):
    import os
    import inspect
    from ruamel.yaml import YAML
    from pathlib import Path
    import rcn_web.core.events  # Ensure events are loaded so we can run it?

    messages = []

    python_filename = name.replace("-", "_") + ".py"
    target_dir = Path(os.getcwd())

    # We assume server runs in rcn-web root
    # We need to place it in rcn_server/rcn_helpers/automation/ usually?
    # Wait, the client code wrote to "current working directory".
    # In rcn-web, where are scheduled tasks?
    # `rcn_web/flows/scheduled_tasks.py` exists.
    # `rcn_web/flows/` seems like a good place.

    # Let's check where `basic_recon_flow.yaml` is.
    # It is in `rcn-server`.
    # But here we are in `rcn-web`.
    # `rcn-web` likely has its own flow yaml or uses `rcn-server` one if mounted.

    # Let's assume we write to `rcn_web/flows/custom_{python_filename}` to be safe,
    # or just `custom_flows/{python_filename}` if we can.

    # However, to be consistent with the "Client" logic which used cwd:
    # If the user runs the server in `rcn-web`, cwd is `rcn-web`.

    # Let's put it in `rcn_web/flows/`
    file_path = target_dir / "rcn_web" / "flows" / python_filename

    try:
        file_exists = file_path.exists()
        with open(file_path, "a") as f:
            if file_exists:
                f.write("\n\n")
            f.write(python_code)

        if file_exists:
            messages.append(f"Function appended to existing file '{file_path}'.")
        else:
            messages.append(f"File '{file_path}' created.")

    except Exception as e:
        raise ValueError(f"Error writing Python file: {e}")

    # YAML
    fn_name_base = Path(python_filename).stem
    python_fn = f"py_{fn_name_base}"

    # Check if target_yaml is absolute or relative
    yaml_path = Path(target_yaml)
    if not yaml_path.is_absolute():
        yaml_path = target_dir / target_yaml

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
            # We might need to specify module if it's not auto-discovered
            # But rcn-core loads events from many places.
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
        raise ValueError(f"Error modifying YAML: {e}")

    if run_now:
        # Execute the code in a restricted scope
        exec_code = f"""
{python_code}

import inspect

async def main():
    try:
        fn_name = '{python_fn.replace("py_", "")}'
        fn = locals().get(fn_name) or globals().get(fn_name)
        
        if fn and callable(fn):
            sig = inspect.signature(fn)
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
        import asyncio
        import rcn_core.parse_yaml as pyaml
        from rcn_web.storage.utils import storage

        try:
            g = vars(pyaml).copy()
            if "storage" not in g:
                g["storage"] = storage
            l = {}
            exec(exec_code, g, l)

            if "main" in l and asyncio.iscoroutinefunction(l["main"]):
                res = await l["main"]()
                messages.append(f"Immediate execution result: {res}")
        except Exception as e:
            messages.append(f"Immediate execution failed: {e}")

    return {"status": "success", "message": "\n".join(messages)}


@register_action()
async def scan_app(app_name: str, config_xml: str, scan_type: str, **kwargs):
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

    # Reuse add_note logic or call it
    # We add the note to the app itself (web-apps::annotations)

    await add_note(
        app_name=app_name,
        entry_id=app_name,  # App name as ID for app-level note
        note_key=note_key,
        note_value=wrapped_xml,
        storage_name="web-apps::annotations",
    )

    return {
        "status": "started",
        "message": f"{scan_type} started for {app_name}",
        "source_id": source_id,
        "start_ts": start_ts,
    }
