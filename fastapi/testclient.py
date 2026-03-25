from typing import Any, Dict
from . import FastAPI


class TestClient:
    def __init__(self, app: FastAPI):
        self.app = app

    def post(self, path: str, json: Dict[str, Any] | None = None):
        json_body = json or {}
        # Use the FastAPI internal handler
        response = self.app._handle("POST", path, json_body)
        return response
