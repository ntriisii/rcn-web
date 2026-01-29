from .ips import router as ip_router
from .domains import router as domains_router
from .applications import router as app_router
from .storage import router as storage_router
from .test_proxy import router as test_proxy
from .websockets import router as websockets_router

__all__ = ["app_router", "ip_router", "domains_router", "storage_router", "test_proxy", "websockets_router"]
