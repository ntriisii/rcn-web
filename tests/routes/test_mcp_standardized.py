import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from fastapi import FastAPI
    from rcn_web.routes.mcp_api import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

class TestMCPStandardized:
    def test_view_apps_with_filter(self, client):
        mock_storage = MagicMock()
        mock_storage.storage_name = "web-apps"
        mock_storage.get_view_data.return_value = [{"id": 1, "site": "test.com"}]
        mock_storage.compile_query.return_value = ("main.id = ?", [1])
        mock_storage.primary_key = "id"
        mock_storage.use_main_alias = True
        
        mock_target = MagicMock()
        mock_target.targets = {} # Not a MultiTargetStorage for this test
        mock_target.get_storage_create.return_value = mock_storage
        
        with patch("rcn_web.routes.mcp_api.get_storage", return_value=mock_target):
            response = client.post("/mcp/view", json={
                "collection": "web-apps",
                "filter": "entry['id'] == 1"
            })
            assert response.status_code == 200
            assert "site: test.com" in response.text

    def test_preview_flows(self, client):
        mock_storage = MagicMock()
        mock_storage.storage_name = "flows"
        mock_storage.get_text_preview.return_value = "Storage: flows\nEntries: 10"
        
        with patch("rcn_web.core.utils.RemoteFlowsAdapter.get_instance", return_value=mock_storage):
            response = client.post("/mcp/preview", json={
                "collection": "flows"
            })
            assert response.status_code == 200
            assert "Storage: flows" in response.text
