import sys
import os
import pathlib
import aiohttp
import aiofiles as aiof

from urllib.parse import urlparse

from rcn_web.core.utils import get_root_storage
from rcn_core.storage.bases import get_storage_create
import rcn_core.globals


def js_url_to_local_file(js_url, app_name):
    parsed = urlparse(js_url)
    path = parsed.path
    base = sys.argv[1]

    path = os.path.join(base, "js", app_name, path[1:])
    os.makedirs(os.path.dirname(path), exist_ok=True)

    return path


async def run_js_files_analysis(site, js_urls):
    print(js_urls)
    async with aiohttp.ClientSession() as session:
        # FIXME: sometimes the files change you need to take care of that
        new_locations = []
        for js_url in js_urls:
            js_location = js_url_to_local_file(js_url, site)
            print("enumerating", js_location, pathlib.Path(js_location).exists())
            print(js_url)
            if not pathlib.Path(js_location).exists():
                new_locations.append(js_location)
                print("trying to get the freaking resp")
                async with session.get(js_url) as resp:
                    print("trying to download js file, status: ", resp.status)
                    if (
                        "4" in str(resp.status)
                        or "5" in str(resp.status)
                        or "javascript" not in resp.headers["content-type"]
                    ):
                        return

                    content = await resp.content.read()
                    async with aiof.open(js_location, "wb") as f:
                        await f.write(content)

        if new_locations:
            await js_analysis_run_flow_on_files(new_locations, site)


async def js_analysis_run_flow_on_files(paths, app_name):
    flow = rcn_core.globals.RCN_FLOWS["js-analysis-with-jsluice"]()
    collected_paths = " ".join(paths)
    flow.set_data([collected_paths])
    out = await flow.run()

    st = get_root_storage()

    # NOTE: the app would be already created from the caller function
    app = get_app_by_site(st, app_name)

    js_storage = get_storage_create("web-apps::js-analysis", parent_id=app['id'])
    js_storage.add_many(out, source="jsluice")
