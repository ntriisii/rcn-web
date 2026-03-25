import asyncio
from typing import Callable, Dict, Any, List, Tuple


class JSONResponse:
    def __init__(self, content: Any, status_code: int = 200):
        self._content = content
        self.status_code = status_code

    def json(self):
        return self._content


class Request:
    def __init__(self, json_data: Dict[str, Any]):
        self._json = json_data

    async def json(self):
        return self._json


class APIRouter:
    def __init__(self, prefix: str = ""):
        self.prefix = prefix.rstrip("/")
        self.routes: List[Tuple[str, str, Callable]] = []

    def post(self, path: str):
        def decorator(func: Callable):
            full_path = (
                f"{self.prefix}{path}"
                if path.startswith("/")
                else f"{self.prefix}/{path}"
            )
            self.routes.append(("POST", full_path, func))
            return func

        return decorator


class FastAPI:
    def __init__(self):
        self._routes: Dict[Tuple[str, str], Callable] = {}

    def include_router(self, router: APIRouter):
        for method, path, handler in router.routes:
            self._routes[(method, path)] = handler

    def _handle(self, method: str, path: str, json_body: Dict[str, Any]):
        handler = self._routes.get((method, path))
        if not handler:
            raise ValueError(f"No route for {method} {path}")

        request = Request(json_body)

        result = asyncio.get_event_loop().run_until_complete(handler(request))
        return result


__all__ = ["FastAPI", "APIRouter", "JSONResponse", "Request"]
