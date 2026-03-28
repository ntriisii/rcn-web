import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from rcn_web.routes.mcp_api import router as mcp_router

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(mcp_router)
    return TestClient(app)

def test_describe_target_no_storage(client):
    with patch("rcn_web.core.utils.get_storage", return_value=None):
        response = client.post("/mcp/describe-target", json={"target": "some-id"})
        assert response.status_code == 404
        assert response.json() == {"error": "No target storage found"}

def test_describe_target_success(client):
    mock_target_storage = MagicMock()
    mock_target_storage.id = "target-123"
    mock_target_storage.site = "example.com"
    
    # Mock for storages
    mock_st = MagicMock()
    mock_st.__len__.return_value = 5
    mock_st.get.return_value = [{"col1": "val1", "col2": "val2"}]
    
    with (
        patch("rcn_web.core.utils.get_storage", return_value=mock_target_storage),
        patch("rcn_core.storage.bases.get_storage_create", return_value=mock_st),
        patch("rcn_web.core.utils.web_match_storage", return_value=[{"storage": mock_st}])
    ):
        response = client.post("/mcp/describe-target", json={"target": "target-123"})
        assert response.status_code == 200
        data = response.json()
        assert data["target"]["id"] == "target-123"
        assert data["target"]["site"] == "example.com"
        assert "web-apps" in data["storages"]
        assert data["storages"]["web-apps"]["count"] == 5
        assert data["storages"]["web-apps"]["columns"] == ["col1", "col2"]
        assert "flows" in data["storages"]
        assert data["storages"]["flows"]["count"] == 5

def test_describe_target_partial_failure(client):
    mock_target_storage = MagicMock()
    mock_target_storage.id = "target-123"
    
    def side_effect(name, **kwargs):
        if name == "web-apps":
            mock_st = MagicMock()
            mock_st.__len__.return_value = 1
            mock_st.get.return_value = [{"id": 1}]
            return mock_st
        raise Exception("Storage error")

    with (
        patch("rcn_web.core.utils.get_storage", return_value=mock_target_storage),
        patch("rcn_core.storage.bases.get_storage_create", side_effect=side_effect),
        patch("rcn_web.core.utils.web_match_storage", side_effect=Exception("Flow error"))
    ):
        response = client.post("/mcp/describe-target", json={"target": "target-123"})
        assert response.status_code == 200
        data = response.json()
        assert data["storages"]["web-apps"]["count"] == 1
        assert "error" in data["storages"]["web-apps::app-links"]
        assert data["storages"]["web-apps::app-links"]["error"] == "Storage error"
        assert data["storages"]["flows"]["error"] == "Flow error"
