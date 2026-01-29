import aiohttp
import asyncio
import requests

from fastapi import APIRouter
from fastapi.responses import JSONResponse

import rcn_core.globals

from rcn_web import storage


router = APIRouter(prefix="/ips")
target_storage = rcn_core.globals.TARGET_STORAGE


@router.get("/getIPsData")
async def get_ips() -> JSONResponse:
    ips = target_storage.ips
    ip_data = target_storage.ip_storage.get()
    return JSONResponse(ip_data)


@router.post("/addIPshodanData")
async def add_shodan_ip_data(ip: str, shodan_data: dict) -> JSONResponse:
    asyncio.create_task(
        target_storage.ip_storage.add_shodan_scanning_data(ip, shodan_data)
    )
    return JSONResponse({"added": True})


@router.get("/getIPCensysData")
def get_ip_censys_data(ip: str):
    ip_storage = target_storage.ip_storage
    found_data = []
    for d in ip_storage._censys_data:
        if d.get("ip", "") == ip:
            found_data.append(d)

    return JSONResponse(found_data)


@router.get("/clearShodanIPs")
def clear_shodan_ips():
    ip_storage = storage().get_storage_create("shodan-scrapped-ips")
    ip_storage.clear()
    ip_storage.storage_md_set("shodan-last-scanned-index", 0)
