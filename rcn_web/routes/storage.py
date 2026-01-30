import json

from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi import APIRouter

from rcn_web import *
from rcn_web.storage.utils import (
    get_storage_data as get_storage_data_matching,
)

router = APIRouter(prefix="/storage")


# TODO: more directed errors


@router.post("/getContent")
async def get_storage_data(req: Request):
    content = await req.json()
    query_string = content.get("query-string")
    ev = content.get("query-expression")
    if type(ev) == str:
        ev = compile(ev, "<string>", "eval")

    return JSONResponse(get_data_storages_matching(query_string, ev))

    # return JSONResponse('error while processing the query', status_code=400, )
    # data = get_data_storages_matching(query_string, ev)

    # return JSONResponse(data)


@router.post("/addContent")
async def add_storage_data(req: Request):
    content = await req.json()
    data = content.get("data")
    storage_index = content.get("query-string")

    try:
        add_to_data_storage(storage_index, data)
    except:
        return JSONResponse(
            "error while processing the query",
            status_code=400,
        )


@router.post("/delContent")
async def del_storage(req: Request):
    content = await req.json()
    storage_index = content.get("query-string")
    ev = content.get("query-expression")
    del_storage_data(storage_index, ev)


@router.post("/modifyContent")
async def modify_storage(req: Request):
    content = await req.json()
    storage_index = content.get("query-string")
    ev = content.get("query-expression")
    ex = content.get("exec-expression")

    modify_storage_data(storage_index, ev, ex)


@router.post("/addStorageSourcesPreviewData")
async def add_storage_sources_data(req: Request):
    content = await req.json()
    data = content.get("data")
    storage_index = content.get("query-string")

    source_key = content["key"]
    source_value = content["value"]
    data_storages = get_storage_data_matching(storage_index)
    for s in data_storages:
        s[source_key] = eval(source_value)


@router.post("/addEntryAnnotation")
async def add_entry_annotation(req: Request):
    from rcn_core.storage.bases import add_annotation as global_add_annotation, get_storage_create
    content = await req.json()
    app_names = content.get("app_name")
    app_ids = content.get("app_id")
    storage_names = content.get("storage_name")
    entry_id = content.get("entry_id")
    key = content.get("key")
    value = content.get("value")
    
    if isinstance(app_names, str): app_names = [app_names]
    if isinstance(app_ids, (str, int)): app_ids = [app_ids]
    if isinstance(storage_names, str): storage_names = [storage_names]
    
    target = storage() 
    added_annotations = []
    
    # Prioritize app_ids if present, otherwise use app_names
    identifiers = app_ids if app_ids else (app_names or [None])
    is_id = bool(app_ids)
    
    for ident in identifiers:
        for storage_name in (storage_names or ["web-apps::annotations"]):
            if storage_name == "web-apps":
                # In the 'web-apps' view, the entry_id is the application site.
                # We want to add a note to the application itself.
                # If ident is None (target level?), usually entry_id is the site.
                # But here we are adding to an entry.
                # If we are in 'web-apps' storage (list of apps), entry_id should be app ID or site.
                # Currently entry_id is passed from frontend.
                
                app = get_app_by_site(target, entry_id) if isinstance(entry_id, (int, str)) and str(entry_id).isdigit() else target, entry_id
                if app:
                    nid = global_add_annotation(entry_id=entry_id, storage_name=storage_name, key=key, value=value, parent_id=app['id'])
                    added_annotations.append({
                        "app_site": app.get('site'),
                        "annotation_id": nid,
                        "storage": "web-apps"
                    })
            else:
                if ident: 
                    app = get_app_by_site(target, ident) if is_id else target, ident
                else: 
                    app = target
                
                if app:
                    parent_id = app.get('id') if isinstance(app, dict) else getattr(app, 'id', None)
                    nid = global_add_annotation(entry_id=entry_id, storage_name=storage_name, key=key, value=value, parent_id=parent_id)
                    added_annotations.append({
                        "app_site": app.get('site') if isinstance(app, dict) else None,
                        "annotation_id": nid,
                        "storage": storage_name
                    })

    return JSONResponse({"count": len(added_annotations), "annotations": added_annotations})

