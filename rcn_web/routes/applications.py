import base64
import asyncio
import re
import pathlib
import aiohttp

from urllib.parse import urlparse
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import JSONResponse, HTMLResponse

import rcn_core.globals

from rcn_web.core.utils import get_storage, get_target_storage
from rcn_core.storage.target_storage import MultiTargetStorage as TargetStorage
from rcn_web.storage.url.utils import add_gau_entries

# from rcn_web.proxy.collect_js import handle_collected_js_files
from rcn_web.storage.fuzzing import handle_fuzzing_entries
from rcn_web.storage.url.utils import http_raw_request_to_flow

# from rcn_web.storage.url import handle_crawling_collected_urls
from rcn_web.storage.vuln_scanning import handle_scanning_entries


router = APIRouter(prefix="/apps")


@router.post("/urls/addGauCollectedData")
async def add_gau_collected_data(request: Request) -> JSONResponse:
    content = await request.json()
    data = content["data"]

    asyncio.create_task(add_gau_entries(data))

    return JSONResponse({"added": True})


# @router.post('/urls/setApplicationGauCollectedURLs')
# async def set_app_gau_urls(request:Request)->JSONResponse:
#   content = await request.json()
#   data = content['data']
#   app_name = content['application']

#   # get the application
#   st = get_storage()
#   app = get_app_by_site(st, app_name)

#   if not app: app = get_app_by_site(st, app_name)
#   if not app: return JSONResponse({'added': False}, status_code=404)

#   wayback_storage = app.get_storage_create('wayback-urls')
#   wayback_storage.set_storage_data(data)
#   wayback_storage.storage_md_set('wayback-fetched-all', True)

#   return JSONResponse({'added': True})


# @router.post("/urls/addCrawlingData")
# async def get_crawled_data(request:Request)->JSONResponse:
#   content = await request.json()
#   data = content['data']

#   asyncio.create_task(handle_crawling_collected_urls(data))

#   return JSONResponse({'added': True})


# @router.get("/js/updateJsFileContent")
# async def update_js_file(file_path:str):

#   relative_file_path = re.sub(".*?/js/", "", file_path, 1)
#   app_name = relative_file_path.split('/')[0]
#   app = get_app_by_site(get_storage(), app_name)
#   if not app:
#     # TODO: error ??
#     return

#   # NOTE: the collected data on the data file would be deduplicated
#   # when we create teh ID for the entry so we don't need to worry
#   # about it

#   # update the old file in directory to be .js.bk
#   file_path_obj = pathlib.Path(file_path)
#   file_path_obj.rename(file_path_obj.as_posix() + ".bk")

#   # NOTE: when we repeat the request the server would automatically
#   # collect the content from the new file and store it in the server

#   # get the request related to the js file so that we repeat the
#   # sname request with custom headers and cookies
#   app_links_storage = app['app-links']
#   js_file_remote_path = '/'.join(relative_file_path.split('/')[1:])
#   link_obj = app_links_storage.get(f"'{js_file_remote_path}' in e['path']")
#   base_url = app.scheme + "://" + app.site

#   if not link_obj:
#     raw_request = (
#       f"GET /{js_file_remote_path} HTTP/1.1\n"
#       f"host: {app.site}\n"
#       "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36\n\n"
#     )

#   else:
#     link_obj = link_obj[0]
#     raw_request = link_obj['raw-request']

#   request_flow = http_raw_request_to_flow(base_url, raw_request)

#   # repeat the request using the proxy the proxy will extract
#   # and handle the request
#   session = aiohttp.ClientSession()
#   resp = await session.post(
#     url="http://localhost:8082/repeatRequest",
#     json=request_flow
#   )

#   resp_content = await resp.json()
#   resp_content = resp_content[-1]

#   await session.close()

#   body = base64.b64decode(resp_content['response-body']).decode('utf-8')
#   url_for_js_location = re.sub(":[0-9]+","",base_url)+'/'+js_file_remote_path
#   await handle_collected_js_files(
#     dict(),
#     [{'url': url_for_js_location, 'response': body}]
#   )

# # split the raw request and create
# #################################
# # vuln scanning fuzzing etc
# #################################


# @router.post('/addFuzzingData')
# async def add_fuzzing_data(request:Request)->JSONResponse:
#   content = await request.json()
#   data = content['data']

#   asyncio.create_task(handle_fuzzing_entries(data))

#   return JSONResponse({'added': True})


# @router.post('/addNucleiScanningData')
# async def add_scanning_data(request:Request)->JSONResponse:
#   content = await request.json()

#   asyncio.create_task(handle_scanning_entries(content ))

#   return JSONResponse({'added': True})


#################################
# vuln scanning fuzzing etc
#################################


#################################
# configs for applications
#################################
@router.post("/addAnnotation")
async def add_annotation(request: Request) -> JSONResponse:
    from rcn_core.storage.bases import add_annotation as global_add_annotation

    content = await request.json()
    site = content.get("site")
    entry_id = content.get("entry_id")
    key = content.get("key")
    value = content.get("value")
    storage_name = content.get("storage", "web-apps::annotations")

    app = get_app_by_site(get_target_storage(), site)
    if not app:
        return JSONResponse({"added": False, "error": "App not found"}, status_code=404)

    # Use global add_annotation
    global_add_annotation(
        entry_id=entry_id,
        storage_name=storage_name,
        key=key,
        value=value,
        parent_id=app["id"],
    )

    return JSONResponse({"added": True})


@router.post("/getAnnotations")
async def get_annotations(request: Request) -> JSONResponse:
    from rcn_core.storage.bases import get_storage_create

    content = await request.json()
    site = content.get("site")
    entry_id = content.get("entry_id")
    storage_name = content.get("storage", "web-apps::annotations")

    app = get_app_by_site(get_target_storage(), site)
    if not app:
        return JSONResponse(
            {"annotations": [], "error": "App not found"}, status_code=404
        )

    st_list = get_storage_create(storage_name, parent_id=app["id"])
    if not st_list:
        return JSONResponse(
            {"annotations": [], "error": "Storage not found"}, status_code=404
        )
    st = st_list[0]
    annotations = st.get_annotations_for_entry(entry_id)

    return JSONResponse({"annotations": annotations})


from pydantic import BaseModel


class AppPreviewRequest(BaseModel):
    identifiers: list[str | int]


@router.post("/preview_apps")
async def preview_apps(request: AppPreviewRequest):
    from rcn_core.storage.bases import get_storage_create

    st = get_target_storage()
    if not st:
        return JSONResponse("No storage loaded.", status_code=404)

    apps = []
    for ident in request.identifiers:
        found = None
        # Try finding by ID first
        if isinstance(ident, int) or (isinstance(ident, str) and ident.isdigit()):
            found = next(
                (a for a in get_uniq_apps(st) if str(a["id"]) == str(ident)), None
            )

        # If not found or not ID, try by site
        if not found and isinstance(ident, str):
            found = get_app_by_site(st, ident)

        if found:
            if found not in apps:
                apps.append(found)

    if not apps:
        return JSONResponse("No apps found.")

    ai_payload = ""
    for app in apps:
        ai_payload += f"APP ID: {app['id']}\n"
        # Manual text view since Entry is removed
        for k, v in app.items():
            if k not in ["id", "timestamp", "parent_id"]:
                ai_payload += f"{k}: {v}\n"

        ai_payload += "\n\nApplication Annotations:\n"

        ann_st_list = get_storage_create("web-apps::annotations", parent_id=app["id"])
        if ann_st_list:
            ann_st = ann_st_list[0]
            annotations = ann_st.get_all_entries()

            for annotation in annotations:
                ai_payload += f" - [ID: {annotation['id']}] {annotation['key']}: {annotation.get('value', '')}\n"

        ai_payload += "\n#######################\n"

    return JSONResponse(ai_payload)
