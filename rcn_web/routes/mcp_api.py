
from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Optional

from rcn_web.storage.utils import get_storage
from rcn_core.storage.target_storage import TargetStorage
from rcn_core.storage.bases import get_storage_create
from rcn_core.parse_yaml import execute_script
from pydantic import BaseModel

class GenericPreviewRequest(BaseModel):
    type: str  # storage name e.g 'web-apps', 'js-flows', 'app-links'
    ids: Optional[list[int | str]] = None
    parent_id: Optional[int] = None
    page: int = 1
    limit: int = 500
    sql_filter: Optional[str] = None

class GenericViewRequest(BaseModel):
    type: str
    ids: Optional[list[int | str]] = None
    parent_id: Optional[int] = None
    page: int = 1
    limit: int = 500
    sql_filter: Optional[str] = None

class ScriptRequest(BaseModel):
    code: str

class ScanResultsRequest(BaseModel):
    app_site: Optional[str] = None
    app_id: Optional[str | int] = None
    source_name: str
    min_timestamp: float
    scan_type: str

router = APIRouter(prefix="/mcp", tags=["mcp"])

def _resolve_storage(storage_name: str, parent_id: Optional[int | str] = None):
    st = get_storage()
    if not st: 
        return None
    
    # If parent_id is provided, we can directly resolve via the global factory
    # This bypasses potential issues in MultiTargetStorage's default logic
    if parent_id is not None:
        return get_storage_create(storage_name, parent_id=parent_id)

    # If no parent_id, we rely on the storage object to decide context (e.g. default target)
    if hasattr(st, "get_storage_create"):
        try:
            return st.get_storage_create(storage_name)
        except (IndexError, AttributeError):
            # Fallback: if MultiTargetStorage fails to pick a default, we can't do much
            # unless we pick the first target ourselves safely
            if hasattr(st, "targets") and st.targets:
                first_target = next(iter(st.targets.values()))
                return get_storage_create(storage_name, parent_id=first_target.id)
            return None
            
    return None

def _render_storage_view(target_storage, page=1, limit=500, sql_filter=None, is_preview=False):

    if not target_storage: return "Storage not found."

    

    if is_preview: return target_storage.get_text_preview(sql_filter=sql_filter)

    else: return target_storage.get_text_view(page=page, limit=limit, sql_filter=sql_filter)






@router.post("/check_scan_results")
async def check_scan_results(request: ScanResultsRequest):
    from fastapi.responses import JSONResponse
    
    st = get_storage()
    app = None
    if request.app_id:
        app = st, request.app_id
    if not app and request.app_site:
        app = st, request.app_site
        
    if not app: return JSONResponse({"status": "error", "message": "App not found"})
        
    results = []
    
    target_storage_name = None
    if request.scan_type == 'scanning': target_storage_name = "web-apps::nuclei-scanning"
    elif request.scan_type == 'fuzzing': target_storage_name = "web-apps::fuzzing-data"
    else:
        return JSONResponse({"status": "error", "message": "Invalid scan_type. Must be 'scanning' or 'fuzzing'."}, status_code=404)
    
    # Check for data
    st_obj = get_storage_create(target_storage_name, parent_id=app['id'])
    if st_obj:
        sid = st_obj.resolve_source_id(request.source_name)
        if sid:
             entries = st_obj.get_filtered(f"source_id = {sid} AND timestamp >= {request.min_timestamp}")
             if entries: results.extend(entries)

    # If no results found, check for completion annotation
    if not results and st_obj:
        annotations_st = get_storage_create("web-apps::annotations", parent_id=app['id'])
        if annotations_st:
            key = f"scan-result:{request.source_name}"
            completed_annotations = annotations_st.get_filtered(f"key = '{key}' AND storage_name = '{target_storage_name}'")
            if completed_annotations:
                annotation = completed_annotations[0]
                results.append({
                    "info": "Scan completed with no results.",
                    "value": annotation.get("value"),
                    "source_id": request.source_name,
                    "timestamp": annotation.get("timestamp")
                })
                 
    # Format results as text
    if not results: return PlainTextResponse("No new scan results found yet.", status_code=404)
      
    text_output = []
    text_output.append(f"Scan Results for {request.source_name} (Type: {request.scan_type})")
    text_output.append(f"Found {len(results)} entries.")
    text_output.append("")
    
    if results:
        # Determine keys from the first entry
        keys = list(results[0].keys())
        
        # Filter out internal keys if desired, similar to get_text_view
        internal_keys = ['source_id']
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
                val = str(row.get(k, '')).replace('\n', ' ')
                entry_lines.append(val)
            entry_blocks.append("\n".join(entry_lines))
            
        text_output.append("\n##\n".join(entry_blocks))
        
    return PlainTextResponse("\n".join(text_output))


@router.post("/preview/generic")
async def preview_generic(request: GenericPreviewRequest):

    # 1. Resolve Storage
    parent_id = request.parent_id if request.parent_id and request.parent_id != 0 else None
    target_storage = _resolve_storage(request.type, parent_id=parent_id)
    
    if not target_storage:
        return JSONResponse(f"Storage '{request.type}' not found.", status_code=404)

    # 2. Construct Filter
    final_filter = request.sql_filter
    if request.ids:
         ids_str = ",".join([str(i) for i in request.ids if str(i).isdigit()]) # Safety check
         if ids_str:
             id_filter = f"id IN ({ids_str})"
             if final_filter: final_filter = f"({final_filter}) AND {id_filter}"
             else: final_filter = id_filter

    # 3. Return Preview using get_text_preview
    return JSONResponse(_render_storage_view(target_storage, sql_filter=final_filter, is_preview=True))

@router.post("/view/generic")
async def view_generic(request: GenericViewRequest):
    # 1. Resolve Storage
    parent_id = request.parent_id if request.parent_id and request.parent_id != 0 else None
    target_storage = _resolve_storage(request.type, parent_id=parent_id)
    
    if not target_storage:
        return JSONResponse(f"Storage '{request.type}' not found.", status_code=404)
        
    # 2. Construct Filter
    final_filter = request.sql_filter
    if request.ids:
         ids_str = ",".join([str(i) for i in request.ids if str(i).isdigit()])
         if ids_str:
             id_filter = f"id IN ({ids_str})"
             if final_filter: final_filter = f"({final_filter}) AND {id_filter}"
             else: final_filter = id_filter

    # 3. Return View
    return JSONResponse(_render_storage_view(target_storage, page=request.page, limit=request.limit, sql_filter=final_filter))
    

@router.post("/run_script")
async def run_script(request: ScriptRequest):
    import asyncio
    import rcn_core.parse_yaml as pyaml
    from rcn_web.storage.utils import storage
    try:
        # Create execution environment inheriting from parse_yaml globals
        g = vars(pyaml).copy()
        if "storage" not in g: g["storage"] = storage
        
        l = {}
        exec(request.code, g, l)
        
        # Check if an async 'main' function was defined and await it
        if 'main' in l and asyncio.iscoroutinefunction(l['main']):
            res = await l['main']()
            return PlainTextResponse(str(res) if res is not None else "Async execution completed.")
            
        return PlainTextResponse("Script executed successfully.")
    except Exception as e:
        return PlainTextResponse(f"Error executing script: {e}", status_code=500)
