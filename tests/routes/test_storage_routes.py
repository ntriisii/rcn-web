"""Tests for rcn_web.routes.storage and MCP endpoints.

Tests cover:
- /storage/getContent
- /storage/addContent
- /storage/addEntryAnnotation
- /mcp/preview
- /mcp/view
- /mcp/action
"""

import pytest

from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from fastapi import FastAPI
    from rcn_web.routes.storage import router as storage_router
    from rcn_web.routes.mcp_api import router as mcp_router

    app = FastAPI()
    app.include_router(storage_router)
    app.include_router(mcp_router)
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


class TestMcpPreview:
    """Tests for standardized /mcp/preview endpoint."""

    def test_preview_happy_path(self, client):
        mock_st = MagicMock()
        mock_st.storage_name = "web-apps::app-links"
        mock_st.get_text_preview.return_value = "Preview Data"
        
        with patch("rcn_web.routes.mcp_api._resolve_storage_impl", return_value=mock_st):
            response = client.post(
                "/mcp/preview",
                json={"collection": "web-apps::app-links"},
            )
            assert response.status_code == 200
            assert "Preview Data" in response.text


class TestMcpView:
    """Tests for standardized /mcp/view endpoint."""

    def test_view_happy_path(self, client):
        mock_st = MagicMock()
        mock_st.storage_name = "web-apps::app-links"
        mock_st.get_view_data.return_value = [{"id": "entry-1", "url": "https://example.com/page1"}]
        mock_st.compile_query.return_value = ("1=1", [])
        mock_st.primary_key = "id"
        mock_st.use_main_alias = False
        
        with patch("rcn_web.routes.mcp_api._resolve_storage_impl", return_value=mock_st):
            response = client.post(
                "/mcp/view",
                json={"collection": "web-apps::app-links", "page": 1, "limit": 100},
            )
            assert response.status_code == 200
            assert "url: https://example.com/page1" in response.text


class TestMcpAction:
    """Tests for /mcp/action endpoint."""

    def test_action_endpoint(self, client):
        # rcn-core's MCP router handles /action by looking up in the registry
        from rcn_core.mcp.registry import registry
        
        mock_action = MagicMock(return_value={"status": "success"})
        registry.action("test_action")(mock_action)
        
        response = client.post(
            "/mcp/action",
            json={
                "action": "test_action",
                "params": {"foo": "bar"},
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_action.assert_called_once_with(foo="bar")
