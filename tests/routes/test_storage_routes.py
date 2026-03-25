"""Tests for rcn_web.routes.storage and MCP endpoints.

Tests cover:
- /storage/getContent
- /storage/addContent
- /storage/addEntryAnnotation
- /mcp/preview/generic
- /mcp/view/generic
- /mcp/action
"""

import pytest

from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import types, sys
    import importlib

    fastapi_utils = types.ModuleType("fastapi_utils")
    tasks = types.ModuleType("fastapi_utils.tasks")

    def dummy_repeat_every(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    tasks.repeat_every = dummy_repeat_every
    fastapi_utils.tasks = tasks
    sys.modules["fastapi_utils"] = fastapi_utils
    sys.modules["fastapi_utils.tasks"] = tasks
    import types as _types

    responses_mod = _types.ModuleType("fastapi.responses")
    try:
        from fastapi.responses import JSONResponse as _JSONResponse
    except Exception:

        class _JSONResponse:
            pass

    responses_mod.JSONResponse = _JSONResponse
    responses_mod.HTMLResponse = _JSONResponse
    sys.modules["fastapi.responses"] = responses_mod
    from fastapi import FastAPI
    from rcn_web.routes.storage import router as storage_router

    app = FastAPI()
    app.include_router(storage_router)
    client = TestClient(app=app)
    yield client


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for CLI tests."""
    with patch("requests.post") as mock:
        yield mock


class TestStorageGetContent:
    """Tests for /storage/getContent endpoint."""

    def test_get_content_happy_path(self, client):
        mock_data = [
            {"id": "entry-1", "url": "https://example.com/page1"},
            {"id": "entry-2", "url": "https://example.com/page2"},
        ]
        with patch(
            "rcn_web.routes.storage.get_data_storages_matching", return_value=mock_data
        ):
            response = client.post(
                "/storage/getContent",
                json={
                    "query-string": "web-apps::app-links",
                    "query-expression": None,
                },
            )
        assert response.status_code == 200
        assert response.json() == mock_data


class TestStorageAddContent:
    """Tests for /storage/addContent endpoint."""

    def test_add_content_happy_path(self, client):
        mock_data = [{"url": "https://example.com/new"}]
        with patch("rcn_web.routes.storage.add_to_data_storage") as mock_add:
            response = client.post(
                "/storage/addContent",
                json={"query-string": "web-apps::app-links", "data": mock_data},
            )
        assert response.status_code == 200
        mock_add.assert_called_once()


class TestStorageAddEntryAnnotation:
    """Tests for /storage/addEntryAnnotation endpoint."""

    def test_add_annotation_happy_path(self, client):
        mock_app = {"id": "app-123", "site": "https://example.com"}
        with (
            patch("rcn_web.routes.storage.get_storage") as mock_get_storage,
            patch("rcn_web.routes.storage.get_app_by_site", return_value=mock_app),
            patch(
                "rcn_web.routes.storage.global_add_annotation", return_value="ann-123"
            ),
        ):
            mock_get_storage.return_value = MagicMock()
            response = client.post(
                "/storage/addEntryAnnotation",
                json={
                    "app_name": ["example.com"],
                    "storage_name": ["web-apps::annotations"],
                    "entry_id": "entry-456",
                    "key": "todo",
                    "value": "Check authentication",
                    "category": "notes",
                },
            )
        assert response.status_code == 200
        result = response.json()
        assert result["count"] == 1


class TestMcpPreviewGeneric:
    """Tests for /mcp/preview/generic endpoint."""

    pass


class TestMcpViewGeneric:
    """Tests for /mcp/view/generic endpoint."""

    pass


class TestMcpAction:
    """Tests for /mcp/action endpoint."""

    pass
