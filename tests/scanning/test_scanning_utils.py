"""Tests for rcn_web.scanning.utils event handlers.

Tests cover:
- crawl_application
- nuclei_scan_apps
- application_fuzzing

Each handler is tested for:
- Happy Path: Normal execution with valid data
- Empty Input: Early return when no data to process
- Error Path: Exception handling and graceful degradation
"""

import pytest

pytest_plugins = ["pytest_asyncio"]
from unittest.mock import MagicMock, AsyncMock, patch
import json


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
    return {"name": "test-scanner", "event": "test", "metadata": {}}


@pytest.fixture
def mock_scheduled_md():
    """Scheduled metadata dictionary used by scheduled functions."""
    return {"scheduled_time": None, "run_id": "test-run"}


# =============================================================================
# Tests for crawl_application
# =============================================================================


@pytest.mark.asyncio
async def test_crawl_application_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: apps are collected and katana process is started."""
    from rcn_web.scanning.utils import crawl_application

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-123",
                "site": "https://test.example.com",
                "url": "https://test.example.com",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    mock_file = AsyncMock()
    mock_file.write = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.start_scheduled_process", AsyncMock(return_value="")
        ) as mock_process,
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", MagicMock()),
        patch("os.remove", MagicMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await crawl_application(mock_event, mock_scheduled_md)

        mock_process.assert_called_once()
        # Verify katana command is called with the temp file
        call_args = mock_process.call_args[0][0]
        assert "katana" in call_args


@pytest.mark.asyncio
async def test_crawl_application_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed entries."""
    from rcn_web.scanning.utils import crawl_application

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.start_scheduled_process", AsyncMock()
        ) as mock_process,
    ):
        await crawl_application(mock_event, mock_scheduled_md)

        mock_process.assert_not_called()


@pytest.mark.asyncio
async def test_crawl_application_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: apps are collected and katana process is started."""
    from rcn_web.scanning.utils import crawl_application

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-123",
                "site": "https://test.example.com",
                "url": "https://test.example.com",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    mock_file = AsyncMock()
    mock_file.write = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_core.time_event.start_scheduled_process", AsyncMock(return_value="")
        ) as mock_process,
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", MagicMock()),
        patch("os.remove", MagicMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await crawl_application(mock_event, mock_scheduled_md)

        mock_process.assert_called_once()
        call_args = mock_process.call_args[0][0]
        assert "katana" in call_args


@pytest.mark.asyncio
async def test_crawl_application_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed entries."""
    from rcn_web.scanning.utils import crawl_application

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_core.time_event.start_scheduled_process", AsyncMock()
        ) as mock_process,
    ):
        await crawl_application(mock_event, mock_scheduled_md)

        mock_process.assert_not_called()


@pytest.mark.asyncio
async def test_crawl_application_process_error(mock_event, mock_scheduled_md):
    """Test error path: subprocess error propagates but temp file is cleaned up."""
    from rcn_web.scanning.utils import crawl_application

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-123",
                "site": "https://test.example.com",
                "url": "https://test.example.com",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    mock_file = AsyncMock()
    mock_file.write = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_core.time_event.start_scheduled_process",
            AsyncMock(side_effect=RuntimeError("Katana failed")),
        ),
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("os.path.exists", return_value=True),
        patch("os.makedirs", MagicMock()),
        patch("os.remove") as mock_remove,
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(RuntimeError, match="Katana failed"):
            await crawl_application(mock_event, mock_scheduled_md)

        mock_remove.assert_called()


# =============================================================================
# Tests for nuclei_scan_apps
# =============================================================================


@pytest.mark.asyncio
async def test_nuclei_scan_apps_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: apps are collected and nuclei scan runs."""
    from rcn_web.scanning.utils import nuclei_scan_apps

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-456",
                "site": "https://nuclei.example.com",
                "url": "https://nuclei.example.com",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    # Mock nuclei results
    nuclei_result = json.dumps(
        {
            "host": "https://nuclei.example.com",
            "template-id": "CVE-2021-1234",
            "template-path": "/tmp/Templates/http/cves/CVE-2021-1234.yaml",
            "info": {"name": "Test Vulnerability", "severity": "high"},
        }
    )

    mock_file = AsyncMock()
    mock_file.write = AsyncMock()

    mock_app = {"id": "app-456", "site": "https://nuclei.example.com"}
    mock_storage = MagicMock()
    mock_storage.get = MagicMock(return_value=[])

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_nuclei_scan",
            AsyncMock(return_value=nuclei_result),
        ) as mock_nuclei,
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("rcn_web.scanning.utils.get_storage", MagicMock()),
        patch(
            "rcn_web.scanning.utils.get_app_by_site", MagicMock(return_value=mock_app)
        ),
        patch("rcn_web.scanning.utils.get_storage_create", return_value=[mock_storage]),
        patch("rcn_web.scanning.utils.handle_nuclei_scanning_entries", AsyncMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await nuclei_scan_apps(mock_event, mock_scheduled_md)

        mock_nuclei.assert_called_once()


@pytest.mark.asyncio
async def test_nuclei_scan_apps_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed entries."""
    from rcn_web.scanning.utils import nuclei_scan_apps

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.utils.run_nuclei_scan", AsyncMock()) as mock_nuclei,
    ):
        await nuclei_scan_apps(mock_event, mock_scheduled_md)

        mock_nuclei.assert_not_called()


@pytest.mark.asyncio
async def test_nuclei_scan_apps_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: apps are collected and nuclei scan runs."""
    from rcn_web.scanning.utils import nuclei_scan_apps
    import rcn_web.scanning.utils as utils_module

    utils_module.nuclei_args = ""  # type: ignore

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-456",
                "site": "https://nuclei.example.com",
                "url": "https://nuclei.example.com",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    nuclei_result = json.dumps(
        {
            "host": "https://nuclei.example.com",
            "template-id": "CVE-2021-1234",
            "template-path": "/tmp/Templates/http/cves/CVE-2021-1234.yaml",
            "info": {"name": "Test Vulnerability", "severity": "high"},
        }
    )

    mock_file = AsyncMock()
    mock_file.write = AsyncMock()

    mock_app = {"id": "app-456", "site": "https://nuclei.example.com"}
    mock_storage = MagicMock()
    mock_storage.get = MagicMock(return_value=[])

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_nuclei_scan",
            AsyncMock(return_value=nuclei_result),
        ) as mock_nuclei,
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("rcn_web.scanning.utils.get_storage", MagicMock()),
        patch(
            "rcn_web.scanning.utils.get_app_by_site", MagicMock(return_value=mock_app)
        ),
        patch("rcn_web.scanning.utils.get_storage_create", return_value=[mock_storage]),
        patch("rcn_web.scanning.utils.handle_nuclei_scanning_entries", AsyncMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await nuclei_scan_apps(mock_event, mock_scheduled_md)

        mock_nuclei.assert_called_once()

    delattr(utils_module, "nuclei_args")


@pytest.mark.asyncio
async def test_nuclei_scan_apps_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed entries."""
    from rcn_web.scanning.utils import nuclei_scan_apps

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.utils.run_nuclei_scan", AsyncMock()) as mock_nuclei,
    ):
        await nuclei_scan_apps(mock_event, mock_scheduled_md)

        mock_nuclei.assert_not_called()


@pytest.mark.asyncio
async def test_nuclei_scan_apps_no_app_found(mock_event, mock_scheduled_md):
    """Test that handler handles missing app gracefully."""
    from rcn_web.scanning.utils import nuclei_scan_apps
    import rcn_web.scanning.utils as utils_module

    utils_module.nuclei_args = ""  # type: ignore

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-456",
                "site": "https://nuclei.example.com",
                "url": "https://nuclei.example.com",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    nuclei_result = json.dumps(
        {
            "host": "https://nuclei.example.com",
            "template-id": "CVE-2021-1234",
            "template-path": "/tmp/Templates/http/cves/CVE-2021-1234.yaml",
            "info": {"name": "Test Vulnerability", "severity": "high"},
        }
    )

    mock_file = AsyncMock()
    mock_file.write = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_nuclei_scan",
            AsyncMock(return_value=nuclei_result),
        ),
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("rcn_web.scanning.utils.get_storage", MagicMock()),
        patch("rcn_web.scanning.utils.get_app_by_site", MagicMock(return_value=None)),
        patch(
            "rcn_web.scanning.utils.handle_nuclei_scanning_entries", AsyncMock()
        ) as mock_handle,
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await nuclei_scan_apps(mock_event, mock_scheduled_md)

        mock_handle.assert_called_once()

    delattr(utils_module, "nuclei_args")


# =============================================================================
# Tests for application_fuzzing
# =============================================================================


@pytest.mark.asyncio
async def test_application_fuzzing_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: apps are collected and ffuf scan runs."""
    from rcn_web.scanning.utils import application_fuzzing

    mock_event_with_wordlists = {
        **mock_event,
        "remote-wordlist": ["https://example.com/wordlist.txt"],
        "local-wordlists": ["/path/to/local/wordlist.txt"],
    }

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-789",
                "site": "https://fuzz.example.com",
                "url": "https://fuzz.example.com/",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    mock_storage = MagicMock()
    mock_storage.add_many = MagicMock()

    ffuf_results = [
        {"path": "/admin", "status": 200, "words": 10, "lines": 5, "length": 100},
        {"path": "/backup", "status": 403, "words": 5, "lines": 2, "length": 50},
    ]

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_ffuf_scan",
            AsyncMock(return_value=ffuf_results),
        ) as mock_ffuf,
        patch("rcn_web.scanning.utils.get_storage_create", return_value=[mock_storage]),
    ):
        await application_fuzzing(mock_event_with_wordlists, mock_scheduled_md)

        mock_ffuf.assert_called_once()
        mock_storage.add_many.assert_called_once()


@pytest.mark.asyncio
async def test_application_fuzzing_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed entries."""
    from rcn_web.scanning.utils import application_fuzzing

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.utils.run_ffuf_scan", AsyncMock()) as mock_ffuf,
    ):
        await application_fuzzing(mock_event, mock_scheduled_md)

        mock_ffuf.assert_not_called()


@pytest.mark.asyncio
async def test_application_fuzzing_with_valid_200_outliers(
    mock_event, mock_scheduled_md
):
    """Test that handler makes aiohttp requests for valid 200 outliers."""
    from rcn_web.scanning.utils import application_fuzzing

    mock_event_with_wordlists = {
        **mock_event,
        "remote-wordlist": ["https://example.com/wordlist.txt"],
    }

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-789",
                "site": "https://fuzz.example.com",
                "url": "https://fuzz.example.com/",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    mock_storage = MagicMock()
    mock_storage.add_many = MagicMock()

    ffuf_results = [
        {"path": "/admin", "status": 200, "words": 100, "lines": 50, "length": 1000},
        {"path": "/api", "status": 200, "words": 10, "lines": 5, "length": 100},
    ]

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="response content")

    mock_get_context = MagicMock()
    mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_get_context)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_ffuf_scan",
            AsyncMock(return_value=ffuf_results),
        ),
        patch("rcn_web.scanning.utils.get_storage_create", return_value=[mock_storage]),
        patch(
            "rcn_web.scanning.utils.aiohttp.ClientSession", return_value=mock_session
        ),
    ):
        await application_fuzzing(mock_event_with_wordlists, mock_scheduled_md)

        mock_session.get.assert_called()


@pytest.mark.asyncio
async def test_application_fuzzing_aiohttp_error(mock_event, mock_scheduled_md):
    """Test that aiohttp errors are handled gracefully during outlier validation."""
    from rcn_web.scanning.utils import application_fuzzing
    import aiohttp

    mock_event_with_wordlists = {
        **mock_event,
        "remote-wordlist": ["https://example.com/wordlist.txt"],
    }

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-789",
                "site": "https://fuzz.example.com",
                "url": "https://fuzz.example.com/",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    mock_storage = MagicMock()
    mock_storage.add_many = MagicMock()

    ffuf_results = [
        {"path": "/admin", "status": 200, "words": 100, "lines": 50, "length": 1000},
        {"path": "/api", "status": 200, "words": 10, "lines": 5, "length": 100},
    ]

    mock_get_context = MagicMock()
    mock_get_context.__aenter__ = AsyncMock(
        side_effect=aiohttp.ClientError("Connection error")
    )
    mock_get_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_get_context)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_ffuf_scan",
            AsyncMock(return_value=ffuf_results),
        ),
        patch("rcn_web.scanning.utils.get_storage_create", return_value=[mock_storage]),
        patch(
            "rcn_web.scanning.utils.aiohttp.ClientSession", return_value=mock_session
        ),
    ):
        await application_fuzzing(mock_event_with_wordlists, mock_scheduled_md)

        mock_storage.add_many.assert_not_called()


@pytest.mark.asyncio
async def test_application_fuzzing_with_valid_200_outliers(
    mock_event, mock_scheduled_md
):
    """Test that handler makes aiohttp requests for valid 200 outliers."""
    from rcn_web.scanning.utils import application_fuzzing

    mock_event_with_wordlists = {
        **mock_event,
        "remote-wordlist": ["https://example.com/wordlist.txt"],
    }

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-789",
                "site": "https://fuzz.example.com",
                "url": "https://fuzz.example.com/",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    mock_storage = MagicMock()
    mock_storage.add_many = MagicMock()

    # Results with 200 status that are outliers (different response signatures)
    ffuf_results = [
        {"path": "/admin", "status": 200, "words": 100, "lines": 50, "length": 1000},
        {
            "path": "/api",
            "status": 200,
            "words": 10,
            "lines": 5,
            "length": 100,
        },  # outlier
    ]

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="response content")

    mock_get_context = MagicMock()
    mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_get_context)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_ffuf_scan",
            AsyncMock(return_value=ffuf_results),
        ),
        patch("rcn_web.scanning.utils.get_storage_create", return_value=[mock_storage]),
        patch(
            "rcn_web.scanning.utils.aiohttp.ClientSession", return_value=mock_session
        ),
    ):
        await application_fuzzing(mock_event_with_wordlists, mock_scheduled_md)

        # Verify aiohttp session was used for outlier validation
        mock_session.get.assert_called()


@pytest.mark.asyncio
async def test_application_fuzzing_aiohttp_error(mock_event, mock_scheduled_md):
    """Test that aiohttp errors are handled gracefully during outlier validation."""
    from rcn_web.scanning.utils import application_fuzzing
    import aiohttp

    mock_event_with_wordlists = {
        **mock_event,
        "remote-wordlist": ["https://example.com/wordlist.txt"],
    }

    mock_entries = {
        "entry-1": {
            "entry": {
                "id": "app-789",
                "site": "https://fuzz.example.com",
                "url": "https://fuzz.example.com/",
            }
        }
    }

    mock_context = create_mock_context_manager(mock_entries)

    mock_storage = MagicMock()
    mock_storage.add_many = MagicMock()

    # Results with outlier 200 status
    ffuf_results = [
        {"path": "/admin", "status": 200, "words": 100, "lines": 50, "length": 1000},
        {"path": "/api", "status": 200, "words": 10, "lines": 5, "length": 100},
    ]

    mock_session = MagicMock()
    # Ensure any awaited .text calls on a response raise aiohttp.ClientError
    mock_response = MagicMock()
    # .text will raise when awaited
    mock_response.text = AsyncMock(side_effect=aiohttp.ClientError("Connection error"))
    mock_get_context = MagicMock()
    # __aenter__ returns the mock_response
    mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_get_context.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_get_context)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.utils.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.utils.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_ffuf_scan",
            AsyncMock(return_value=ffuf_results),
        ),
        patch("rcn_web.scanning.utils.get_storage_create", return_value=[mock_storage]),
        patch(
            "rcn_web.scanning.utils.aiohttp.ClientSession", return_value=mock_session
        ),
    ):
        # Should not raise
        await application_fuzzing(mock_event_with_wordlists, mock_scheduled_md)
