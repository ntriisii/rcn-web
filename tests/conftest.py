import pytest  # type: ignore
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path


class MockTargetStorage:
    """A lightweight mock of TargetStorage with async methods used in tests."""

    def __init__(self):
        # Provide a dummy target directory Path
        self.target_directory = Path("/tmp/mock_target")
        # Async methods commonly accessed
        self.get_storage_create = AsyncMock(return_value=MagicMock())
        self.storage_md_set = AsyncMock()
        self.storage_md_get = AsyncMock(return_value={})
        self.storage_md_del = AsyncMock()
        self.storage_md_exists = AsyncMock(return_value=False)
        # Add any additional async stubs as needed


@pytest.fixture
def mock_target_storage():
    """Fixture returning a MockTargetStorage instance."""
    return MockTargetStorage()


@pytest.fixture
def mock_event():
    """Minimal event dictionary for @rcn_event handlers."""
    return {"event": "test", "metadata": {}}


@pytest.fixture
def mock_scheduled_md():
    """Scheduled metadata dictionary used by scheduled functions."""
    return {"scheduled_time": None, "run_id": "test-run"}


@pytest.fixture
def mock_web_match_storage(monkeypatch):
    """Patch ``rcn_web.core.utils.web_match_storage`` with a dummy async function.

    The dummy simply returns a ``MagicMock`` instance so callers can inspect it.
    """

    async def dummy_web_match_storage(*args, **kwargs):
        return MagicMock()

    monkeypatch.setattr("rcn_web.core.utils.web_match_storage", dummy_web_match_storage)
    return dummy_web_match_storage
