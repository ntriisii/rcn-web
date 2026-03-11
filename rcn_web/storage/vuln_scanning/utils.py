import os
import validators

from collections import defaultdict
from urllib.parse import urlparse

from rcn_web.core.utils import get_storage, get_app_by_site
from rcn_core.storage.bases import get_storage_create


def get_nuclei_host_and_path(nuclei_host):
    nuclei_host = nuclei_host.strip(".")
    if validators.domain(nuclei_host):
        return nuclei_host.strip("."), "/"
    elif validators.url(nuclei_host):
        p = urlparse(nuclei_host)
        return (p.netloc, p.path + ("?" + p.query if p.query else ""))
    elif validators.ipv4(nuclei_host):
        return nuclei_host, "/"
    elif validators.ipv6(nuclei_host):
        return nuclei_host, "/"

    # check for something like domain:port
    else:
        return nuclei_host, "/"


async def handle_scanning_entries(content):
    vuln_scanned = content[
        "url-vuln-scanned"
    ]  # used with nuclei fuzzing templates for URLs
    content = content["data"]
    # should not do this but there must be a problem with httpx for example
    if not content:
        return
    tmpl_dir = os.path.expanduser("~/AllForOne/Templates/")
    found_apps = defaultdict(list)
    for entry in content:
        site, path = get_nuclei_host_and_path(entry["host"])
        entry = {
            "template-id": entry["template-id"],
            "template-path": entry["template-path"].replace(
                "/tmp/Templates/", tmpl_dir
            ),
            "description": entry["info"].get("description", ""),
            "name": entry["info"].get("name", ""),
            "tags": entry["info"].get("tags", []),
            "severity": entry["info"].get("severity", "unknwon"),
            "host": entry["host"],
        }

        found_apps[site].append(entry)

    s = get_storage()
    for site in found_apps:
        app = get_app_by_site(s, site)
        data = found_apps[site]

        if not app:
            # Skip if not found
            continue

        # get the URL storage related to the application and
        # create if not there and store the vulns there
        src_url_storage = get_storage_create("web-apps::app-links", parent_id=app['id'])
        url_entries = src_url_storage.get()

        # store in the app scanning data only if the target path is /
        nc_storage = get_storage_create("web-apps::nuclei-scanning", parent_id=app['id'])
        site_vuln_ids = [i["template-id"] for i in nc_storage.get()]
        for entry in data:
            host, path = get_nuclei_host_and_path(entry["host"])
            print("adding nuclei data related to ", host, path)
            if path == "/" or path == "":
                if not any(entry["template-id"] == i for i in site_vuln_ids):
                    nc_storage.add_many([entry], source="")
                    site_vuln_ids.append(entry["template-id"])

            else:
                # assume the URL is there
                for uentry in url_entries:
                    if uentry["path"] == path and uentry["method"] == "GET":

                        # check the vuln checked if it is checked
                        uentry["vuln-checked"] = vuln_scanned

                        if not any(
                            entry["template-id"] == i["template-id"]
                            for i in uentry["found-vulns"]
                        ):
                            uentry["found-vulns"].append(entry)
