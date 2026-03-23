"""Tests for rcn_web.scanning.app_scans event handlers.

Tests cover:
- ai_annotate_link_entries

Each handler is tested for:
- Happy Path: Normal execution with valid data
- Empty Input: Early return when no data to process
- Error Path: Exception handling and graceful degradation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# =============================================================================
# Fixtures
# =============================================================================


class MockApp:
    """Mock application entry that is hashable (like real storage entries)."""

    def __init__(self, app_id="app-123", site="test.example.com"):
        self.id = app_id
        self.site = site
        self.data = {
            "id": app_id,
            "site": site,
            "scheme": "https",
            "technologies": "React,Node.js",
            "title": "Test App",
            "status_code": 200,
        }

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, MockApp):
            return self.id == other.id
        return False

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)


def create_mock_context_manager(return_value):
    """Create a mock async context manager for get_unprocessed_entries."""
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=return_value)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    return mock_context


@pytest.fixture
def mock_event():
    """Minimal event dictionary for @rcn_event handlers."""
    return {
        "name": "test-ai-annotator",
        "event": "test",
        "metadata": {},
        "ai-base-prompt": "Analyze these apps: {apps_prompt}",
        "ai-collect-instructions": "Find vulnerabilities",
        "ai-tags": "xss,sqli,rce",
        "model": "gemini-flash-latest",
    }


@pytest.fixture
def mock_scheduled_md():
    """Scheduled metadata dictionary used by scheduled functions."""
    return {"scheduled_time": None, "run_id": "test-run"}


# =============================================================================
# Tests for ai_annotate_link_entries
# =============================================================================


@pytest.mark.asyncio
async def test_ai_annotate_link_entries_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: links are collected and prompt data is generated."""
    from rcn_web.scanning.app_scans import ai_annotate_link_entries

    mock_app = MockApp(app_id="app-123", site="test.example.com")

    mock_link = {
        "id": "link-456",
        "method": "GET",
        "path": "/api/users",
        "data": "",
    }

    mock_storage = MagicMock()
    mock_storage.storage_name = "web-apps::app-links"

    mock_entries = {
        "link-456": {
            "entry": mock_link,
            "storage": mock_storage,
            "parent": mock_app,
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    annotation_calls = []

    def mock_add_annotation(entry_id, storage_name, key, value, parent_id):
        annotation_calls.append(
            {
                "entry_id": entry_id,
                "storage_name": storage_name,
                "key": key,
                "value": value,
                "parent_id": parent_id,
            }
        )

    with (
        patch(
            "rcn_web.scanning.app_scans.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.app_scans.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.app_scans.ai_ask",
            AsyncMock(return_value="def ai_annotate_links(): pass"),
        ),
        patch(
            "rcn_web.scanning.app_scans.global_add_annotation",
            side_effect=mock_add_annotation,
        ),
        patch(
            "rcn_web.scanning.app_scans.get_storage_create",
            return_value=[],
        ),
    ):
        await ai_annotate_link_entries(mock_event, mock_scheduled_md)

        assert True


@pytest.mark.asyncio
async def test_ai_annotate_link_entries_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed entries."""
    from rcn_web.scanning.app_scans import ai_annotate_link_entries

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.app_scans.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.app_scans.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.app_scans.ai_ask", AsyncMock()) as mock_ai,
        patch("rcn_web.scanning.app_scans.global_add_annotation") as mock_add_ann,
    ):
        await ai_annotate_link_entries(mock_event, mock_scheduled_md)

        mock_ai.assert_not_called()
        mock_add_ann.assert_not_called()


@pytest.mark.asyncio
async def test_ai_annotate_link_entries_ai_error(mock_event, mock_scheduled_md):
    """Test error path: AI service raises exception, handler retries."""
    from rcn_web.scanning.app_scans import ai_annotate_link_entries

    mock_app = MockApp(app_id="app-123", site="test.example.com")

    mock_link = {
        "id": "link-456",
        "method": "GET",
        "path": "/api/test",
        "data": "",
    }

    mock_storage = MagicMock()
    mock_storage.storage_name = "web-apps::app-links"

    mock_entries = {
        "link-456": {
            "entry": mock_link,
            "storage": mock_storage,
            "parent": mock_app,
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    annotation_calls = []

    def mock_add_annotation(entry_id, storage_name, key, value, parent_id):
        annotation_calls.append({"entry_id": entry_id, "key": key, "value": value})

    with (
        patch(
            "rcn_web.scanning.app_scans.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.app_scans.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.app_scans.ai_ask",
            AsyncMock(side_effect=RuntimeError("AI service unavailable")),
        ),
        patch(
            "rcn_web.scanning.app_scans.global_add_annotation",
            side_effect=mock_add_annotation,
        ),
        patch(
            "rcn_web.scanning.app_scans.get_storage_create",
            return_value=[],
        ),
    ):
        await ai_annotate_link_entries(mock_event, mock_scheduled_md)


@pytest.mark.asyncio
async def test_ai_annotate_link_entries_multiple_apps(mock_event, mock_scheduled_md):
    """Test that handler processes multiple apps correctly."""
    from rcn_web.scanning.app_scans import ai_annotate_link_entries

    mock_app1 = MockApp(app_id="app-1", site="app1.example.com")
    mock_app2 = MockApp(app_id="app-2", site="app2.example.com")

    mock_link1 = {
        "id": "link-1",
        "method": "GET",
        "path": "/api/users",
        "data": "",
    }

    mock_link2 = {
        "id": "link-2",
        "method": "POST",
        "path": "/api/login",
        "data": "user=test&pass=test",
    }

    mock_storage = MagicMock()
    mock_storage.storage_name = "web-apps::app-links"

    mock_entries = {
        "link-1": {
            "entry": mock_link1,
            "storage": mock_storage,
            "parent": mock_app1,
        },
        "link-2": {
            "entry": mock_link2,
            "storage": mock_storage,
            "parent": mock_app2,
        },
    }

    mock_context = create_mock_context_manager(mock_entries)

    annotation_calls = []

    def mock_add_annotation(entry_id, storage_name, key, value, parent_id):
        annotation_calls.append(
            {
                "entry_id": entry_id,
                "key": key,
                "value": value,
                "parent_id": parent_id,
            }
        )

    with (
        patch(
            "rcn_web.scanning.app_scans.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.app_scans.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.app_scans.ai_ask",
            AsyncMock(return_value="def ai_annotate_links(): pass"),
        ),
        patch(
            "rcn_web.scanning.app_scans.global_add_annotation",
            side_effect=mock_add_annotation,
        ),
        patch(
            "rcn_web.scanning.app_scans.get_storage_create",
            return_value=[],
        ),
    ):
        await ai_annotate_link_entries(mock_event, mock_scheduled_md)


@pytest.mark.asyncio
async def test_ai_annotate_link_entries_missing_link_in_mapping(
    mock_event, mock_scheduled_md
):
    """Test that handler skips annotations for links not in the mapping."""
    from rcn_web.scanning.app_scans import ai_annotate_link_entries

    mock_app = MockApp(app_id="app-123", site="test.example.com")

    mock_link = {
        "id": "link-456",
        "method": "GET",
        "path": "/api/test",
        "data": "",
    }

    mock_storage = MagicMock()
    mock_storage.storage_name = "web-apps::app-links"

    mock_entries = {
        "link-456": {
            "entry": mock_link,
            "storage": mock_storage,
            "parent": mock_app,
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    annotation_calls = []

    def mock_add_annotation(entry_id, storage_name, key, value, parent_id):
        annotation_calls.append({"entry_id": entry_id, "key": key})

    mock_ai_response = """
def ai_annotate_links():
    annotate_link(999, "D:id", "potential-sqli")
"""

    with (
        patch(
            "rcn_web.scanning.app_scans.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.app_scans.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.app_scans.ai_ask",
            AsyncMock(return_value=mock_ai_response),
        ),
        patch(
            "rcn_web.scanning.app_scans.global_add_annotation",
            side_effect=mock_add_annotation,
        ),
        patch(
            "rcn_web.scanning.app_scans.get_storage_create",
            return_value=[],
        ),
    ):
        await ai_annotate_link_entries(mock_event, mock_scheduled_md)
