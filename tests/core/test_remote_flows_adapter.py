import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from rcn_web.core.utils import RemoteFlowsAdapter


@pytest.fixture(autouse=True)
def reset_adapter_singleton():
    """Reset the RemoteFlowsAdapter singleton before each test."""
    RemoteFlowsAdapter._instance = None
    yield
    RemoteFlowsAdapter._instance = None


@pytest.mark.asyncio
async def test_adapter_initialization_persistence():
    """Verify RemoteFlowsAdapter persists the server start timestamp."""
    with (
        patch("rcn_web.core.utils.StorageMetaData.storage_md_get") as mock_get,
        patch("rcn_web.core.utils.StorageMetaData.storage_md_set") as mock_set,
        patch("rcn_web.core.utils.get_storage", return_value=MagicMock(id=1)),
    ):
        mock_get.return_value = None
        adapter = RemoteFlowsAdapter.get_instance()

        assert adapter._server_start_ts > 0
        mock_set.assert_any_call("server-start-timestamp", adapter._server_start_ts)

        RemoteFlowsAdapter._instance = None
        persisted_ts = 123456789.0
        mock_get.return_value = persisted_ts

        adapter = RemoteFlowsAdapter.get_instance()
        assert adapter._server_start_ts == persisted_ts


@pytest.mark.asyncio
async def test_add_many_triggers_events():
    """Verify add_many triggers event processing for new entries."""
    adapter = RemoteFlowsAdapter.get_instance()
    test_flows = [
        {"timestamp": 100, "url": "http://test1.com"},
        {"timestamp": 101, "url": "http://test2.com"},
    ]

    with patch("rcn_core.data_access.process_new_entries_for_events") as mock_process:
        adapter.add_many(test_flows)

        # Give asyncio tasks a moment to run
        await asyncio.sleep(0.1)

        mock_process.assert_called_once()
        assert len(adapter._cache) == 2
        assert adapter._last_fetch_ts == 101


@pytest.mark.asyncio
async def test_add_many_deduplication():
    """Verify add_many only adds flows newer than the current cache."""
    adapter = RemoteFlowsAdapter.get_instance()
    adapter._cache = [{"timestamp": 200, "id": 200}]
    adapter._last_fetch_ts = 200

    test_flows = [
        {"timestamp": 199, "url": "old"},
        {"timestamp": 200, "url": "current"},
        {"timestamp": 201, "url": "new"},
    ]

    with patch("rcn_core.data_access.process_new_entries_for_events") as mock_process:
        added = adapter.add_many(test_flows)

        assert len(added) == 1
        assert added[0]["timestamp"] == 201
        assert len(adapter._cache) == 2
        assert adapter._last_fetch_ts == 201


@pytest.mark.asyncio
async def test_fetch_all_required_events_initializes_consumers():
    """Verify consumers with 0 timestamp are initialized to server start."""
    adapter = RemoteFlowsAdapter.get_instance()
    adapter._server_start_ts = 500.0

    mock_consumer = MagicMock()
    mock_consumer.fn_name = "test_event"
    mock_consumer.event = {"require-storage": "flows"}

    with (
        patch("rcn_core.time_event.TimeEvent") as mock_te,
        patch("rcn_web.core.utils.StorageMetaData.storage_md_get") as mock_get,
        patch("rcn_web.core.utils.StorageMetaData.storage_md_set") as mock_set,
        patch("aiohttp.ClientSession.get") as mock_http_get,
    ):
        mock_te.return_value._dispatch_fns = [mock_consumer]
        mock_get.side_effect = lambda key: 0 if "test_event" in key else None

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=[])
        mock_http_get.return_value.__aenter__.return_value = mock_resp

        await adapter._fetch_all_required_events()

        mock_set.assert_any_call("test_event-last-id-timestamp", 500.0)


@pytest.mark.asyncio
async def test_cache_cleanup_logic():
    """Verify cache is pruned based on minimum required timestamp."""
    adapter = RemoteFlowsAdapter.get_instance()
    adapter._server_start_ts = 400.0
    adapter._cache = [{"timestamp": 150}, {"timestamp": 250}, {"timestamp": 350}]

    mock_fn1 = MagicMock(fn_name="event1", event={"require-storage": "flows"})
    mock_fn2 = MagicMock(fn_name="event2", event={"require-storage": "flows"})

    with (
        patch("rcn_core.time_event.TimeEvent") as mock_te,
        patch("rcn_web.core.utils.StorageMetaData.storage_md_get") as mock_get,
        patch("aiohttp.ClientSession.get") as mock_http_get,
    ):
        mock_te.return_value._dispatch_fns = [mock_fn1, mock_fn2]

        event1_ts = 300.0
        event2_ts = 350.0
        mock_get.side_effect = lambda key: event1_ts if "event1" in key else event2_ts

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=[])
        mock_http_get.return_value.__aenter__.return_value = mock_resp

        await adapter._fetch_all_required_events()

        # Pruning point is min(min(event_ts), start_ts) = min(300, 400) = 300
        assert len(adapter._cache) == 1
        assert adapter._cache[0]["timestamp"] == 350
