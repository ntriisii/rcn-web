""" Tests for scan_client_side_reflected_content in rcn_web/scanning/client_side.py. """

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class MockBrowserResponse:
    """Mock response from HeadlessBrowser.get()."""

    def __init__(self, text: str):
        self.text = text


class MockHeadlessBrowser:
    """Mock async context manager for HeadlessBrowser."""

    def __init__(self, responses: dict | None = None, raise_error: bool = False):
        """
        Args:
            responses: Dict mapping URLs to response text.
            raise_error: If True, raise exception on get() call.
        """
        self._responses = responses or {}
        self._raise_error = raise_error
        self._get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

    async def get(self, url, timeout=10):
        """Mock browser.get() returning response with text."""
        self._get_calls.append(url)
        if self._raise_error:
            raise RuntimeError("Browser failed to load page")
        # Return response with text that may contain probe
        text = self._responses.get(url, "")
        return MockBrowserResponse(text=text)


class MockParent:
    """Mock parent object with site/scheme/url attributes."""

    def __init__(self, site: str = "example.com", scheme: str = "https", url: str = ""):
        self.site = site
        self.scheme = scheme
        self.url = url or f"{scheme}://{site}"
        self.id = "test-parent-id"

    def __getitem__(self, key):
        if key == "id":
            return self.id
        raise KeyError(key)


class MockStorage:
    """Mock storage object."""

    def __init__(self, storage_name: str = "test-storage"):
        self.storage_name = storage_name


@pytest.mark.asyncio
async def test_scan_client_side_reflected_content_happy_path():
    """Test happy path: reflection detected and annotation added."""
    from rcn_web.scanning.client_side import scan_client_side_reflected_content

    # Setup mock data
    mock_parent = MockParent(site="example.com", scheme="https")
    mock_storage = MockStorage(storage_name="web-apps::test-app")
    mock_ref_storage = MockStorage(storage_name="web-apps::test-app::links")

    # Create note entry with potential-xss key
    mock_note_entry = {"id": "note-1", "key": "potential-xss"}

    # Create referenced entry with path containing query params
    mock_referenced_entry = {"id": "ref-1", "path": "/search?q=test&category=all"}

    # Setup unprocessed entries
    mock_entries = {
        "entry-1": {
            "entry": mock_note_entry,
            "reference": mock_referenced_entry,
            "storage": mock_storage,
            "parent": mock_parent,
            "reference_storage": mock_ref_storage,
        }
    }

    # Create mock context manager for get_unprocessed_entries
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    # Create mock browser that reflects the probe
    browser_calls = []

    def create_browser_with_reflection():
        async def mock_get(url, timeout=10):
            # The source code fuzzes one param at a time with a probe.
            # We need to find which param has the 8-char alphanumeric probe.
            from urllib.parse import urlparse, parse_qs
            import re

            browser_calls.append(url)
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            # Find the probe value (8 char alphanumeric) in params
            probe_pattern = re.compile(r"^[a-zA-Z0-9]{8}$")
            probe_value = None
            for values in params.values():
                if values and probe_pattern.match(values[0]):
                    probe_value = values[0]
                    break
            # Return response with the probe reflected
            return MockBrowserResponse(text=f"Search results for: {probe_value}")

        browser = MagicMock()
        browser.get = AsyncMock(side_effect=mock_get)
        browser.__aenter__ = AsyncMock(return_value=browser)
        browser.__aexit__ = AsyncMock(return_value=None)
        return browser

    mock_browser_instance = create_browser_with_reflection()

    # Track annotation calls
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
            "rcn_web.scanning.client_side.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.client_side.HeadlessBrowser",
            return_value=mock_browser_instance,
        ),
        patch(
            "rcn_web.scanning.client_side.global_add_annotation",
            side_effect=mock_add_annotation,
        ),
    ):
        # Execute
        await scan_client_side_reflected_content(
            {"name": "test-scanner"}, {"run_id": "test-run"}
        )

    # Verify annotation was added for reflection
    assert len(browser_calls) == 2, (
        f"Expected 2 browser calls, got {len(browser_calls)}: {browser_calls}"
    )
    assert len(annotation_calls) == 2, (
        f"Expected 2 annotations, got {len(annotation_calls)}"
    )
    for call in annotation_calls:
        assert call["key"] == "reflection-detected"
        assert call["entry_id"] == "ref-1"
        assert call["value"].startswith("Q:")
        assert call["parent_id"] == "test-parent-id"


@pytest.mark.asyncio
async def test_scan_client_side_reflected_content_empty_entries():
    """Test that scanner returns early when no unprocessed entries."""
    from rcn_web.scanning.client_side import scan_client_side_reflected_content

    # Create mock context manager with empty entries
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value={})
    mock_context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.client_side.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch("rcn_web.scanning.client_side.HeadlessBrowser") as mock_browser_cls,
    ):
        # Execute - should return early without creating browser
        await scan_client_side_reflected_content(
            {"name": "test-scanner"}, {"run_id": "test-run"}
        )

        # Verify browser was NOT instantiated (early return)
        mock_browser_cls.assert_not_called()


@pytest.mark.asyncio
async def test_scan_client_side_reflected_content_no_query_params():
    """Test that scanner skips entries without query parameters."""
    from rcn_web.scanning.client_side import scan_client_side_reflected_content

    mock_parent = MockParent(site="example.com", scheme="https")
    mock_storage = MockStorage(storage_name="web-apps::test-app")

    # Note entry with potential-xss
    mock_note_entry = {"id": "note-1", "key": "potential-xss"}

    # Referenced entry with path WITHOUT query params
    mock_referenced_entry = {"id": "ref-1", "path": "/static/page"}

    mock_entries = {
        "entry-1": {
            "entry": mock_note_entry,
            "reference": mock_referenced_entry,
            "storage": mock_storage,
            "parent": mock_parent,
        }
    }

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    # Track browser get calls
    browser_get_calls = []

    async def mock_browser_get(url, timeout=10):
        browser_get_calls.append(url)
        return MockBrowserResponse(text="")

    mock_browser = MagicMock()
    mock_browser.get = AsyncMock(side_effect=mock_browser_get)
    mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_browser.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.client_side.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.client_side.HeadlessBrowser",
            return_value=mock_browser,
        ),
    ):
        await scan_client_side_reflected_content(
            {"name": "test-scanner"}, {"run_id": "test-run"}
        )

    # Verify no browser.get() calls were made (skipped due to no query params)
    assert len(browser_get_calls) == 0


@pytest.mark.asyncio
async def test_scan_client_side_reflected_content_browser_error():
    """Test error path: browser failure is caught and continues."""
    from rcn_web.scanning.client_side import scan_client_side_reflected_content

    mock_parent = MockParent(site="example.com", scheme="https")
    mock_storage = MockStorage(storage_name="web-apps::test-app")
    mock_ref_storage = MockStorage(storage_name="web-apps::test-app::links")

    mock_note_entry = {"id": "note-1", "key": "potential-xss"}
    mock_referenced_entry = {"id": "ref-1", "path": "/search?q=test"}

    mock_entries = {
        "entry-1": {
            "entry": mock_note_entry,
            "reference": mock_referenced_entry,
            "storage": mock_storage,
            "parent": mock_parent,
            "reference_storage": mock_ref_storage,
        }
    }

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    # Browser that raises error on get()
    async def mock_browser_get(url, timeout=10):
        raise RuntimeError("Browser failed to load page")

    mock_browser = MagicMock()
    mock_browser.get = AsyncMock(side_effect=mock_browser_get)
    mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_browser.__aexit__ = AsyncMock(return_value=None)

    # Track annotation calls
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
            "rcn_web.scanning.client_side.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.client_side.HeadlessBrowser",
            return_value=mock_browser,
        ),
        patch(
            "rcn_web.scanning.client_side.global_add_annotation",
            side_effect=mock_add_annotation,
        ),
    ):
        # Execute - should not raise, error is caught
        await scan_client_side_reflected_content(
            {"name": "test-scanner"}, {"run_id": "test-run"}
        )

    # Verify no annotations were added (error was caught)
    assert len(annotation_calls) == 0


@pytest.mark.asyncio
async def test_scan_client_side_reflected_content_wrong_note_key():
    """Test that scanner skips entries with wrong note key."""
    from rcn_web.scanning.client_side import scan_client_side_reflected_content

    mock_parent = MockParent(site="example.com", scheme="https")
    mock_storage = MockStorage(storage_name="web-apps::test-app")

    # Note entry with WRONG key (not potential-xss)
    mock_note_entry = {"id": "note-1", "key": "other-key"}
    mock_referenced_entry = {"id": "ref-1", "path": "/search?q=test"}

    mock_entries = {
        "entry-1": {
            "entry": mock_note_entry,
            "reference": mock_referenced_entry,
            "storage": mock_storage,
            "parent": mock_parent,
        }
    }

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    browser_get_calls = []

    async def mock_browser_get(url, timeout=10):
        browser_get_calls.append(url)
        return MockBrowserResponse(text="")

    mock_browser = MagicMock()
    mock_browser.get = AsyncMock(side_effect=mock_browser_get)
    mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_browser.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "rcn_web.scanning.client_side.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.client_side.HeadlessBrowser",
            return_value=mock_browser,
        ),
    ):
        await scan_client_side_reflected_content(
            {"name": "test-scanner"}, {"run_id": "test-run"}
        )

    # Verify no browser.get() calls (skipped due to wrong key)
    assert len(browser_get_calls) == 0


@pytest.mark.asyncio
async def test_scan_client_side_reflected_content_no_reflection():
    """Test that no annotation is added when probe is NOT reflected."""
    from rcn_web.scanning.client_side import scan_client_side_reflected_content

    mock_parent = MockParent(site="example.com", scheme="https")
    mock_storage = MockStorage(storage_name="web-apps::test-app")
    mock_ref_storage = MockStorage(storage_name="web-apps::test-app::links")

    mock_note_entry = {"id": "note-1", "key": "potential-xss"}
    mock_referenced_entry = {"id": "ref-1", "path": "/search?q=test"}

    mock_entries = {
        "entry-1": {
            "entry": mock_note_entry,
            "reference": mock_referenced_entry,
            "storage": mock_storage,
            "parent": mock_parent,
            "reference_storage": mock_ref_storage,
        }
    }

    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
    mock_context.__aexit__ = AsyncMock(return_value=None)

    # Browser that does NOT reflect the probe
    async def mock_browser_get(url, timeout=10):
        return MockBrowserResponse(text="Search results - no reflection here")

    mock_browser = MagicMock()
    mock_browser.get = AsyncMock(side_effect=mock_browser_get)
    mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_browser.__aexit__ = AsyncMock(return_value=None)

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
            "rcn_web.scanning.client_side.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.client_side.HeadlessBrowser",
            return_value=mock_browser,
        ),
        patch(
            "rcn_web.scanning.client_side.global_add_annotation",
            side_effect=mock_add_annotation,
        ),
    ):
        await scan_client_side_reflected_content(
            {"name": "test-scanner"}, {"run_id": "test-run"}
        )

    # Verify no annotations (no reflection detected)
    assert len(annotation_calls) == 0
