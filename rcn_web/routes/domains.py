from fastapi import APIRouter
from fastapi.responses import JSONResponse

import rcn_core.globals


router = APIRouter(prefix="/domains")
target_storage = rcn_core.globals.TARGET_STORAGE


@router.get("/getDomains")
def get_domains():
    return JSONResponse(target_storage.domains)


@router.post("/addSecuritytrailsDomains")
def add_securitytrails_domains(data: dict):
    domains = data["domains"]
    in_scope_domains = get_inscope_domains(domains)
    print("adding ", len(in_scope_domains), "domains from Securitytrails")
    target_storage.get_storage_create("domains").add_many(
        in_scope_domains, source="securitytrails"
    )
