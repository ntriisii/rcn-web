import os
import sys
import base64
import random
import json
import aiohttp
import asyncio
import re
import functools
import string
import pathlib
import time
import aiofiles as aiof
from urllib.parse import urlparse
import glob
import hashlib

from collections import defaultdict
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.utils import get_app_by_site


TRF_LAST_CHECK_TIME = time.time()
TRF_CHECK_TIME = 10
TRF_FILE_URL_MAP = dict()
TRF_CONTENT_HASH = []
TRF_RUNNING = False


async def trufflehog_operate(flow):

    global TRF_FILE_URL_MAP

    fname = "".join(random.choice(string.ascii_letters) for i in range(20))
    TRF_FILE_URL_MAP[fname] = flow["url"]

    flow_path = "/tmp/" + fname + ".flow_c"

    await write_trufflehog_flow_content(flow, flow_path)
    return await trufflehog_check_for_secrets()


async def trufflehog_check_for_secrets():

    global TRF_LAST_CHECK_TIME, TRF_CHECK_TIME, TRF_FILE_URL_MAP, TRF_CONTENT_HASH, TRF_RUNNING

    # dont hog the system with the processes
    ctime = time.time()
    if (
        ctime - TRF_LAST_CHECK_TIME < TRF_CHECK_TIME
        or len(TRF_FILE_URL_MAP.keys()) < 200
        or TRF_RUNNING
    ):
        return

    TRF_RUNNING = True
    TRF_LAST_CHECK_TIME = ctime
    # check with trufflehog
    out_file_path = "/tmp/truffle_out_" + "".join(
        random.choice(string.ascii_letters) for i in range(5)
    )

    # stored files in the tmp dir
    files = glob.glob("/tmp/*.flow_c")
    print("running trufflehog on ", len(files))

    if not files:
        return

    proc = await asyncio.subprocess.create_subprocess_shell(
        cmd=f"trufflehog filesystem /tmp/*.flow_c --json --no-update > {out_file_path}",
        shell=True,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=sys.stderr,
    )

    await proc.wait()

    content = []
    async with aiof.open(out_file_path, "r") as f:
        content = []
        fcontent = (await f.read()).split("\n")
        for i in fcontent:
            i = i.strip()
            if i:
                try:
                    jc = json.loads(i)
                    fname = (
                        jc["SourceMetadata"]["Data"]["Filesystem"]["file"]
                        .replace(".flow_c", "")
                        .replace("/tmp/", "")
                    )
                    jc["base-url"] = TRF_FILE_URL_MAP.get(fname, "unkown-url")
                    content.append(jc)

                except json.JSONDecodeError:
                    print(f"there was an error decoding trufflehog{i}")

        os.remove(out_file_path)
        TRF_FILE_URL_MAP = dict()

        # remove all flow files in the tmp dir
        # MAYBE: who gives a fuck
        for file in files:
            os.remove(file)

        TRF_RUNNING = False

        if content:
            return content


async def write_trufflehog_flow_content(flow, flow_path):

    async with aiof.open(flow_path, "w") as f:
        rheaders = flow["request-headers"]
        rcontent = flow["request-body"]
        resheaders = flow["response-headers"]
        rescontent = flow["response-body"]
        req_header = "\n".join(i[0] for i in rheaders.values())
        res_headers = "\n".join(i[0] for i in resheaders.values())

        url = flow["url"]
        content = f"""
    {url}
    {rcontent}
    {req_header}
    {res_headers}
    {rescontent}
    """

        # check if the resposne is already in the hashed values to not bother checking again
        chash = hashlib.md5(content.encode("utf-8", "backslashescape")).digest()
        if chash not in TRF_CONTENT_HASH:
            TRF_CONTENT_HASH.append(chash)
            await f.write(content)

        return content


async def trufflehog_store_data(s, extractor, all_content):

    # collect applications
    found_apps = defaultdict(list)
    for entry in all_content["data"]:
        site = urlparse(entry["base-url"]).netloc
        found_apps[site].append(entry)

    for site in found_apps:
        app = get_app_by_site(s, site)
        data = found_apps[site]
        if not app:
            app = get_app_by_site(s, site)

        # just store in the target secrets
        if not app:
            st = s.get_storage_create("trufflehog-secrets")
            st.add_many(
                [
                    {
                        "base-url": i["url"],
                        "DetectorName": i["DetectorName"],
                        "Raw": i["Raw"],
                    }
                    for i in data
                ],
                source="trufflehog",
            )
            continue

        st = get_storage_create("web-apps::trufflehog-secrets", parent_id=app['id'])
        st.add_many(
            [
                {
                    "base-url": i["url"],
                    "DetectorName": i["DetectorName"],
                    "Raw": i["Raw"],
                }
                for i in data
            ],
            source="trufflehog",
        )
