"""Tests for rcn_web.scanning.js_analysis event handlers.

Tests cover:
- js_intelligence_monitor

Each handler is tested for:
- Happy Path: Normal execution with valid data
- Empty Input: Early return when no data to process
- Error Path: Exception handling and graceful degradation
"""

import pytest

pytest.skip("Work in progress", allow_module_level=True)
from unittest.mock import MagicMock, AsyncMock, patch
import pytest_asyncio


# =============================================================================
# Fixtures
# =============================================================================


def create_mock_context_manager(return_value):
    """Create a mock async context manager for get_unprocessed_entries."""
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=return_value)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    return mock_context


@pytest.fixture
def mock_event():
    """Minimal event dictionary for @rcn_event handlers."""
    return {"name": "test-js-monitor", "event": "test", "metadata": {}}


@pytest.fixture
def mock_scheduled_md():
    """Scheduled metadata dictionary used by scheduled functions."""
    return {"scheduled_time": None, "run_id": "test-run"}


# =============================================================================
# Tests for js_intelligence_monitor
# =============================================================================


@pytest.mark.asyncio
async def test_js_intelligence_monitor_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: JS links are processed and inventory entries are stored."""
    from rcn_web.scanning.js_analysis import js_intelligence_monitor

    mock_app = {
        "id": "app-js-123",
        "site": "https://js.example.com",
        "url": "https://js.example.com",
    }
    mock_js_link = {
        "id": "link-1",
        "url": "https://js.example.com/script.js",
        "flow-id": "flow-abc123",
    }

    mock_entries = {"link-1": {"entry": mock_js_link, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    # Mock storage
    mock_js_inventory = MagicMock()
    mock_js_inventory.add_many = MagicMock()
    mock_js_inventory.get_filtered = MagicMock(return_value=[])

    # Mock RemoteFlowsAdapter
    mock_adapter = MagicMock()
    mock_adapter.get_flows_by_id = AsyncMock(
        return_value=[{"response-body": "var x = 1;"}]
    )

    # Mock aiohttp session
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="var x = 1;")

    mock_get_context = MagicMock()
    mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_get_context)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.js_analysis.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.js_analysis.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.js_analysis.RemoteFlowsAdapter.get_instance",
            return_value=mock_adapter,
        ),
        patch("rcn_web.scanning.js_analysis.is_in_scope", return_value=True),
        patch(
            "rcn_web.scanning.js_analysis.get_js_hash",
            AsyncMock(return_value="abc123hash"),
        ),
        patch("rcn_web.scanning.js_analysis.is_third_party", return_value=False),
        patch(
            "rcn_web.scanning.js_analysis.get_storage_create",
            return_value=mock_js_inventory,
        ),
        patch(
            "rcn_web.scanning.js_analysis.aiohttp.ClientSession",
            return_value=mock_session,
        ),
    ):
        await js_intelligence_monitor(mock_event, mock_scheduled_md)

    # Verify storage was called
    mock_js_inventory.add_many.assert_called_once()
    call_args = mock_js_inventory.add_many.call_args[0][0]
    assert len(call_args) == 1
    assert call_args[0]["url"] == "https://js.example.com/script.js"
    assert call_args[0]["hash"] == "abc123hash"
    assert call_args[0]["status"] == "monitored"


@pytest.mark.asyncio
async def test_js_intelligence_monitor_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed entries."""
    from rcn_web.scanning.js_analysis import js_intelligence_monitor

    mock_context = create_mock_context_manager({})

    mock_js_inventory = MagicMock()

    with (
        patch(
            "rcn_web.scanning.js_analysis.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.js_analysis.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.js_analysis.get_storage_create",
            return_value=mock_js_inventory,
        ) as mock_storage_create,
    ):
        await js_intelligence_monitor(mock_event, mock_scheduled_md)

    # Verify storage was never created
    mock_storage_create.assert_not_called()


@pytest.mark.asyncio
async def test_js_intelligence_monitor_out_of_scope(mock_event, mock_scheduled_md):
    """Test that JS links outside scope are skipped."""
    from rcn_web.scanning.js_analysis import js_intelligence_monitor

    mock_app = {
        "id": "app-js-456",
        "site": "https://js.example.com",
        "url": "https://js.example.com",
    }
    mock_js_link = {
        "id": "link-2",
        "url": "https://external.cdn.com/script.js",
        "flow-id": "flow-def456",
    }

    mock_entries = {"link-2": {"entry": mock_js_link, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_js_inventory = MagicMock()

    with (
        patch(
            "rcn_web.scanning.js_analysis.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.js_analysis.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.js_analysis.is_in_scope", return_value=False),
        patch(
            "rcn_web.scanning.js_analysis.get_storage_create",
            return_value=mock_js_inventory,
        ) as mock_storage_create,
    ):
        await js_intelligence_monitor(mock_event, mock_scheduled_md)

    # Verify storage was never created (no inventory entries)
    mock_storage_create.assert_not_called()


@pytest.mark.asyncio
async def test_js_intelligence_monitor_missing_url(mock_event, mock_scheduled_md):
    """Test that entries without URL are skipped."""
    from rcn_web.scanning.js_analysis import js_intelligence_monitor

    mock_app = {
        "id": "app-js-789",
        "site": "https://js.example.com",
        "url": "https://js.example.com",
    }
    mock_js_link = {
        "id": "link-3",
    }

    mock_entries = {"link-3": {"entry": mock_js_link, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_js_inventory = MagicMock()

    with (
        patch(
            "rcn_web.scanning.js_analysis.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.js_analysis.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.js_analysis.get_storage_create",
            return_value=mock_js_inventory,
        ) as mock_storage_create,
    ):
        await js_intelligence_monitor(mock_event, mock_scheduled_md)

    mock_storage_create.assert_not_called()


@pytest.mark.asyncio
async def test_js_intelligence_monitor_unchanged_hash(mock_event, mock_scheduled_md):
    """Test that unchanged JS hash does not create new inventory entry."""
    from rcn_web.scanning.js_analysis import js_intelligence_monitor

    mock_app = {
        "id": "app-js-unchanged",
        "site": "https://js.example.com",
        "url": "https://js.example.com",
    }
    mock_js_link = {
        "id": "link-unchanged",
        "url": "https://js.example.com/old.js",
        "flow-id": "flow-unchanged",
    }

    mock_entries = {"link-unchanged": {"entry": mock_js_link, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_js_inventory = MagicMock()
    mock_js_inventory.get_filtered = MagicMock(
        return_value=[{"url": "https://js.example.com/old.js", "hash": "samehash"}]
    )
    mock_js_inventory.add_many = MagicMock()

    mock_adapter = MagicMock()
    mock_adapter.get_flows_by_id = AsyncMock(
        return_value=[{"response-body": "var old = 1;"}]
    )

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.js_analysis.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.js_analysis.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.js_analysis.RemoteFlowsAdapter.get_instance",
            return_value=mock_adapter,
        ),
        patch("rcn_web.scanning.js_analysis.is_in_scope", return_value=True),
        patch(
            "rcn_web.scanning.js_analysis.get_js_hash",
            AsyncMock(return_value="samehash"),
        ),
        patch("rcn_web.scanning.js_analysis.is_third_party", return_value=False),
        patch(
            "rcn_web.scanning.js_analysis.get_storage_create",
            return_value=mock_js_inventory,
        ),
        patch(
            "rcn_web.scanning.js_analysis.aiohttp.ClientSession",
            return_value=mock_session,
        ),
    ):
        await js_intelligence_monitor(mock_event, mock_scheduled_md)

    mock_js_inventory.add_many.assert_not_called()


@pytest.mark.asyncio
async def test_js_intelligence_monitor_fetch_error(mock_event, mock_scheduled_md):
    """Test that fetch errors are handled gracefully."""
    from rcn_web.scanning.js_analysis import js_intelligence_monitor

    mock_app = {
        "id": "app-js-error",
        "site": "https://js.example.com",
        "url": "https://js.example.com",
    }
    mock_js_link = {
        "id": "link-error",
        "url": "https://js.example.com/error.js",
        "flow-id": None,
    }

    mock_entries = {"link-error": {"entry": mock_js_link, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_js_inventory = MagicMock()

    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=RuntimeError("Network error"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.js_analysis.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.js_analysis.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.js_analysis.is_in_scope", return_value=True),
        patch(
            "rcn_web.scanning.js_analysis.get_storage_create",
            return_value=mock_js_inventory,
        ) as mock_storage_create,
        patch(
            "rcn_web.scanning.js_analysis.aiohttp.ClientSession",
            return_value=mock_session,
        ),
    ):
        await js_intelligence_monitor(mock_event, mock_scheduled_md)

    mock_storage_create.assert_not_called()


@pytest.mark.asyncio
async def test_js_intelligence_monitor_no_content(mock_event, mock_scheduled_md):
    """Test that entries with no content are skipped."""
    from rcn_web.scanning.js_analysis import js_intelligence_monitor

    mock_app = {
        "id": "app-js-nocontent",
        "site": "https://js.example.com",
        "url": "https://js.example.com",
    }
    mock_js_link = {
        "id": "link-nocontent",
        "url": "https://js.example.com/empty.js",
        "flow-id": "flow-nocontent",
    }

    mock_entries = {"link-nocontent": {"entry": mock_js_link, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_js_inventory = MagicMock()

    mock_adapter = MagicMock()
    mock_adapter.get_flows_by_id = AsyncMock(return_value=[])

    mock_response = MagicMock()
    mock_response.status = 404

    mock_get_context = MagicMock()
    mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_get_context)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.js_analysis.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.js_analysis.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.js_analysis.RemoteFlowsAdapter.get_instance",
            return_value=mock_adapter,
        ),
        patch("rcn_web.scanning.js_analysis.is_in_scope", return_value=True),
        patch(
            "rcn_web.scanning.js_analysis.get_storage_create",
            return_value=mock_js_inventory,
        ) as mock_storage_create,
        patch(
            "rcn_web.scanning.js_analysis.aiohttp.ClientSession",
            return_value=mock_session,
        ),
    ):
        await js_intelligence_monitor(mock_event, mock_scheduled_md)

    mock_storage_create.assert_not_called()


@pytest.mark.asyncio
async def test_js_intelligence_monitor_multiple_apps(mock_event, mock_scheduled_md):
    """Test handling multiple apps with multiple JS links each."""
    from rcn_web.scanning.js_analysis import js_intelligence_monitor

    mock_app1 = {
        "id": "app-multi-1",
        "site": "https://app1.example.com",
        "url": "https://app1.example.com",
    }
    mock_app2 = {
        "id": "app-multi-2",
        "site": "https://app2.example.com",
        "url": "https://app2.example.com",
    }

    mock_entries = {
        "link-1": {
            "entry": {
                "id": "link-1",
                "url": "https://app1.example.com/a.js",
                "flow-id": "f1",
            },
            "parent": mock_app1,
        },
        "link-2": {
            "entry": {
                "id": "link-2",
                "url": "https://app1.example.com/b.js",
                "flow-id": "f2",
            },
            "parent": mock_app1,
        },
        "link-3": {
            "entry": {
                "id": "link-3",
                "url": "https://app2.example.com/c.js",
                "flow-id": "f3",
            },
            "parent": mock_app2,
        },
    }
    mock_context = create_mock_context_manager(mock_entries)

    # Track storage creates per app
    storage_creates = {}

    def mock_get_storage_create_fn(name, parent_id):
        if parent_id not in storage_creates:
            storage_creates[parent_id] = MagicMock()
            storage_creates[parent_id].add_many = MagicMock()
            storage_creates[parent_id].get_filtered = MagicMock(return_value=[])
        return storage_creates[parent_id]

    mock_adapter = MagicMock()
    mock_adapter.get_flows_by_id = AsyncMock(
        side_effect=lambda ids: [
            {"response-body": f"content-{i}"} for i, _ in enumerate(ids)
        ]
    )

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="var x = 1;")

    mock_get_context = MagicMock()
    mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_get_context)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.js_analysis.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.js_analysis.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.js_analysis.RemoteFlowsAdapter.get_instance",
            return_value=mock_adapter,
        ),
        patch("rcn_web.scanning.js_analysis.is_in_scope", return_value=True),
        patch(
            "rcn_web.scanning.js_analysis.get_js_hash",
            AsyncMock(side_effect=lambda c: f"hash-{c}"),
        ),
        patch("rcn_web.scanning.js_analysis.is_third_party", return_value=False),
        patch(
            "rcn_web.scanning.js_analysis.get_storage_create",
            side_effect=mock_get_storage_create_fn,
        ),
        patch(
            "rcn_web.scanning.js_analysis.aiohttp.ClientSession",
            return_value=mock_session,
        ),
    ):
        await js_intelligence_monitor(mock_event, mock_scheduled_md)

    # Verify both apps had storage created
    assert "app-multi-1" in storage_creates
    assert "app-multi-2" in storage_creates

    # Verify add_many was called for each app
    storage_creates["app-multi-1"].add_many.assert_called_once()
    storage_creates["app-multi-2"].add_many.assert_called_once()
