import datetime
from urllib.parse import urlparse

from rcn_web.core.utils import get_target_storage, get_app_by_site
from rcn_core.storage.bases import get_storage_create


async def handle_fuzzing_entries(content):
    if not content:
        return
    site = content[0]["host"]
    st = get_target_storage()
    app = get_app_by_site(st, site)

    if not app:
        return

    fz_storage_list = get_storage_create("web-apps::fuzzing-data", parent_id=app["id"])
    if fz_storage_list:
        fz_storage = fz_storage_list[0]
        to_add = [
            {
                "path": urlparse(i["url"]).path,
                "status": i["status"],
                "response-hash": i["lines"] + i["length"] + i["words"],
            }
            for i in content
        ]

        fz_storage.add_many(to_add)
