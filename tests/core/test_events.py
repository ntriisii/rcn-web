import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from pathlib import Path
import datetime

from rcn_web.core.events import handle_init_target


class MockFlow:
    """Mock flow object for testing."""

    def __init__(self, return_value=None):
        self._return_value = return_value or []
        self._data = None

    def set_data(self, data):
        self._data = data

    async def run(self):
        return self._return_value


class MockTargetEntry:
    """Mock target entry for get_unprocessed_entries context manager."""

    def __init__(self):
        self.id = "test-target-id"
        self.target_directory = Path("/tmp/mock_target")
        self.config = {
            "scope": {"wildcards": ["*.example.com"], "urls": ["https://example.com"]}
        }
        self._storage_md = {}
        self._storage_create_mock = MagicMock()

    def storage_md_get(self, key):
        return self._storage_md.get(key)

    def storage_md_set(self, key, value):
        self._storage_md[key] = value


@pytest.mark.asyncio
async def test_handle_init_target_happy_path():
    """Test happy path: flow runs, domains written to file, storage updated."""
    mock_target = MockTargetEntry()
    mock_flow = MockFlow(return_value=["sub.example.com", "api.example.com"])

    # Create mock context manager for get_unprocessed_entries
    mock_entries = {"test-target": {"entry": mock_target}}

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    # Mock storage for domains
    mock_domains_storage = MagicMock()
    mock_domains_storage.add_many = MagicMock()

    with (
        patch("rcn_web.core.events.get_unprocessed_entries", return_value=mock_context),
        patch("rcn_web.core.events.RCN_FLOWS", {"init-flow": lambda: mock_flow}),
        patch(
            "rcn_web.core.events.get_config_wildcards", return_value=["*.example.com"]
        ),
        patch(
            "rcn_web.core.events.get_config_urls", return_value=["https://example.com"]
        ),
        patch(
            "rcn_web.core.events.get_storage_create", return_value=mock_domains_storage
        ),
        patch("rcn_web.core.events.storage_automation_md_get_create", return_value={}),
        patch("builtins.open", mock_open()) as mock_file_open,
        patch("rcn_web.core.events.uniq") as mock_uniq,
        patch("rcn_web.core.events.datetime") as mock_datetime,
    ):
        mock_uniq.side_effect = lambda x: list(dict.fromkeys(x))
        mock_datetime.datetime.now.return_value.timestamp.return_value = 1234567890.0

        # Execute
        await handle_init_target({"event": "test"}, {"run_id": "test-run"})

        # Verify metadata flags
        assert mock_target._storage_md.get("init-recon-running") is False
        assert mock_target._storage_md.get("init-recon-finished") is True
        assert mock_target._storage_md.get("init-recon-started-time") == 1234567890.0

        # Verify file was opened for writing
        mock_file_open.assert_called_once()
        call_args = mock_file_open.call_args
        assert "domains.txt" in str(call_args[0][0])

        # Verify storage was updated with domains
        mock_domains_storage.add_many.assert_called_once()
        call_kwargs = mock_domains_storage.add_many.call_args
        assert call_kwargs[1]["source"] == "init-domains"


@pytest.mark.asyncio
async def test_handle_init_target_empty_entries():
    """Test that handler returns early when no unprocessed entries."""
    # Create mock context manager with empty entries
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value={})
    mock_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "rcn_web.core.events.get_unprocessed_entries", return_value=mock_context
    ):
        # Execute - should return early without error
        await handle_init_target({"event": "test"}, {"run_id": "test-run"})


@pytest.mark.asyncio
async def test_handle_init_target_already_finished():
    """Test that handler skips targets already marked as finished."""
    mock_target = MockTargetEntry()
    mock_target._storage_md["init-recon-finished"] = True

    mock_entries = {"test-target": {"entry": mock_target}}

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "rcn_web.core.events.get_unprocessed_entries", return_value=mock_context
    ):
        # Execute - should skip without processing
        await handle_init_target({"event": "test"}, {"run_id": "test-run"})

        # Verify no flow was run (metadata unchanged)
        assert mock_target._storage_md.get("init-recon-running") is None


@pytest.mark.asyncio
async def test_handle_init_target_already_running():
    """Test that handler skips targets already running."""
    mock_target = MockTargetEntry()
    mock_target._storage_md["init-recon-running"] = True

    mock_entries = {"test-target": {"entry": mock_target}}

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "rcn_web.core.events.get_unprocessed_entries", return_value=mock_context
    ):
        # Execute - should skip without processing
        await handle_init_target({"event": "test"}, {"run_id": "test-run"})


@pytest.mark.asyncio
async def test_handle_init_target_no_flow():
    """Test that handler skips when init-flow is not in RCN_FLOWS."""
    mock_target = MockTargetEntry()

    mock_entries = {"test-target": {"entry": mock_target}}

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("rcn_web.core.events.get_unprocessed_entries", return_value=mock_context),
        patch("rcn_web.core.events.RCN_FLOWS", {}),
    ):
        # Execute - should skip without processing
        await handle_init_target({"event": "test"}, {"run_id": "test-run"})

        # Verify no metadata was set
        assert mock_target._storage_md.get("init-recon-running") is None


@pytest.mark.asyncio
async def test_handle_init_target_error_path():
    """Test error path: exception raised, running flag reset, exception re-raised."""
    mock_target = MockTargetEntry()
    mock_flow = MockFlow()
    mock_flow.run = AsyncMock(side_effect=RuntimeError("Flow execution failed"))

    mock_entries = {"test-target": {"entry": mock_target}}

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("rcn_web.core.events.get_unprocessed_entries", return_value=mock_context),
        patch("rcn_web.core.events.RCN_FLOWS", {"init-flow": lambda: mock_flow}),
        patch(
            "rcn_web.core.events.get_config_wildcards", return_value=["*.example.com"]
        ),
        patch(
            "rcn_web.core.events.get_config_urls", return_value=["https://example.com"]
        ),
    ):
        # Execute - should raise the exception
        with pytest.raises(RuntimeError, match="Flow execution failed"):
            await handle_init_target({"event": "test"}, {"run_id": "test-run"})

        # Verify running flag was reset
        assert mock_target._storage_md.get("init-recon-running") is False
        # Verify finished flag was NOT set
        assert mock_target._storage_md.get("init-recon-finished") is None
