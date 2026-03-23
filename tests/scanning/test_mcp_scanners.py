"""Tests for rcn_web.scanning.mcp_scanners event handlers.

Tests cover:
- mcp_ai_tag_apps_for_scanning
- mcp_interactive_ai_process_todo_notes
- mcp_ai_perform_scanning
- mcp_ai_perform_fuzzing

Each handler is tested for:
- Happy Path: Normal execution with valid data
- Empty Input: Early return when no data to process
- Error Path: Exception handling and graceful degradation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from pathlib import Path
import json


# =============================================================================
# Fixtures
# =============================================================================


class MockApp:
    """Mock application entry for testing."""

    def __init__(self, site="https://example.com", app_id="test-app-id"):
        self.id = app_id
        self.site = site
        self.url = site
        self.data = {"id": app_id, "site": site, "url": site}


class MockAnnotation:
    """Mock annotation entry for testing."""

    def __init__(self, key="todo", value="test value", ann_id="test-ann-id"):
        self.id = ann_id
        self.key = key
        self.value = value


def create_mock_context_manager(return_value):
    """Create a mock async context manager for get_unprocessed_* functions."""
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
# Tests for mcp_ai_tag_apps_for_scanning
# =============================================================================


@pytest.mark.asyncio
async def test_mcp_ai_tag_apps_for_scanning_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: apps are collected and sent to AI service."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_tag_apps_for_scanning

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

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.mcp_server_user_interaction",
            AsyncMock(return_value={"finished": True}),
        ) as mock_interaction,
    ):
        await mcp_ai_tag_apps_for_scanning(mock_event, mock_scheduled_md)

        mock_interaction.assert_called_once()
        call_args = mock_interaction.call_args[0][0]
        assert "Applications to Analyze" in call_args
        assert "app-123" in call_args


@pytest.mark.asyncio
async def test_mcp_ai_tag_apps_for_scanning_empty_entries(
    mock_event, mock_scheduled_md
):
    """Test that handler returns early when no unprocessed entries."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_tag_apps_for_scanning

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.mcp_server_user_interaction", AsyncMock()
        ) as mock_interaction,
    ):
        await mcp_ai_tag_apps_for_scanning(mock_event, mock_scheduled_md)

        mock_interaction.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_ai_tag_apps_for_scanning_empty_apps_list(
    mock_event, mock_scheduled_md
):
    """Test that handler returns early when apps list is empty after extraction."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_tag_apps_for_scanning

    mock_entries = {}
    mock_context = create_mock_context_manager(mock_entries)

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.mcp_server_user_interaction", AsyncMock()
        ) as mock_interaction,
    ):
        await mcp_ai_tag_apps_for_scanning(mock_event, mock_scheduled_md)

        mock_interaction.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_ai_tag_apps_for_scanning_interaction_failure(
    mock_event, mock_scheduled_md
):
    """Test error path: AI interaction returns False/None."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_tag_apps_for_scanning

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

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_entries",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.mcp_server_user_interaction",
            AsyncMock(return_value=False),
        ),
    ):
        await mcp_ai_tag_apps_for_scanning(mock_event, mock_scheduled_md)


# =============================================================================
# Tests for mcp_interactive_ai_process_todo_notes
# =============================================================================


@pytest.mark.asyncio
async def test_mcp_interactive_ai_process_todo_notes_happy_path(
    mock_event, mock_scheduled_md
):
    """Test happy path: todo annotations are collected and sent to AI service."""
    from rcn_web.scanning.mcp_scanners import mcp_interactive_ai_process_todo_notes

    mock_app = {
        "id": "app-456",
        "site": "https://todo.example.com",
        "url": "https://todo.example.com",
    }
    mock_annotation = {
        "id": "ann-1",
        "key": "todo-check-auth",
        "value": "Check authentication bypass",
    }

    mock_entries = {"ann-1": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.mcp_server_user_interaction",
            AsyncMock(return_value={"finished": True}),
        ) as mock_interaction,
    ):
        await mcp_interactive_ai_process_todo_notes(mock_event, mock_scheduled_md)

        mock_interaction.assert_called_once()
        call_args = mock_interaction.call_args[0][0]
        assert "TODO" in call_args
        assert "todo-check-auth" in call_args


@pytest.mark.asyncio
async def test_mcp_interactive_ai_process_todo_notes_empty_entries(
    mock_event, mock_scheduled_md
):
    """Test that handler returns early when no unprocessed annotations."""
    from rcn_web.scanning.mcp_scanners import mcp_interactive_ai_process_todo_notes

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.mcp_server_user_interaction", AsyncMock()
        ) as mock_interaction,
    ):
        await mcp_interactive_ai_process_todo_notes(mock_event, mock_scheduled_md)

        mock_interaction.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_interactive_ai_process_todo_notes_non_todo_keys_filtered(
    mock_event, mock_scheduled_md
):
    """Test that annotations without 'todo' key prefix are filtered out."""
    from rcn_web.scanning.mcp_scanners import mcp_interactive_ai_process_todo_notes

    mock_app = {
        "id": "app-456",
        "site": "https://todo.example.com",
        "url": "https://todo.example.com",
    }

    mock_entries = {
        "ann-1": {
            "entry": {"id": "ann-1", "key": "other-key", "value": "Some value"},
            "parent": mock_app,
        }
    }
    mock_context = create_mock_context_manager(mock_entries)

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.mcp_server_user_interaction", AsyncMock()
        ) as mock_interaction,
    ):
        await mcp_interactive_ai_process_todo_notes(mock_event, mock_scheduled_md)

        mock_interaction.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_interactive_ai_process_todo_notes_interaction_error(
    mock_event, mock_scheduled_md
):
    """Test error path: AI interaction returns None."""
    from rcn_web.scanning.mcp_scanners import mcp_interactive_ai_process_todo_notes

    mock_app = {
        "id": "app-456",
        "site": "https://todo.example.com",
        "url": "https://todo.example.com",
    }
    mock_annotation = {"id": "ann-1", "key": "todo-check", "value": "Check something"}

    mock_entries = {"ann-1": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.mcp_server_user_interaction",
            AsyncMock(return_value=None),
        ),
    ):
        await mcp_interactive_ai_process_todo_notes(mock_event, mock_scheduled_md)


# =============================================================================
# Tests for mcp_ai_perform_scanning
# =============================================================================


@pytest.mark.asyncio
async def test_mcp_ai_perform_scanning_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: scanning annotation is processed and nuclei scan runs."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_scanning

    mock_app = {
        "id": "app-789",
        "site": "https://scan.example.com",
        "url": "https://scan.example.com",
    }
    xml_content = """<scanning>
<base-url>https://scan.example.com/test</base-url>
<templates>http/cves/test.yaml</templates>
</scanning>"""
    mock_annotation = {"id": "ann-scan", "key": "tool-scanning", "value": xml_content}

    mock_entries = {"ann-scan": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_file = AsyncMock()
    mock_file.write = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_nuclei_scan", AsyncMock(return_value="")
        ) as mock_nuclei,
        patch("rcn_web.scanning.utils.handle_nuclei_scanning_entries", AsyncMock()),
        patch("rcn_web.scanning.mcp_scanners.global_add_annotation", MagicMock()),
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("os.path.exists", return_value=True),
        patch("os.remove", MagicMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await mcp_ai_perform_scanning(mock_event, mock_scheduled_md)

        mock_nuclei.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_ai_perform_scanning_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed annotations."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_scanning

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.utils.run_nuclei_scan", AsyncMock()) as mock_nuclei,
    ):
        await mcp_ai_perform_scanning(mock_event, mock_scheduled_md)

        mock_nuclei.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_ai_perform_scanning_invalid_xml(mock_event, mock_scheduled_md):
    """Test error path: invalid XML content is handled gracefully."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_scanning

    mock_app = {
        "id": "app-789",
        "site": "https://scan.example.com",
        "url": "https://scan.example.com",
    }
    mock_annotation = {
        "id": "ann-scan",
        "key": "tool-scanning",
        "value": "<scanning><base-url>https://example.com</base-url>",
    }

    mock_entries = {"ann-scan": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_file = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_nuclei_scan", AsyncMock(return_value="")
        ) as mock_nuclei,
        patch("rcn_web.scanning.utils.handle_nuclei_scanning_entries", AsyncMock()),
        patch("rcn_web.scanning.mcp_scanners.global_add_annotation", MagicMock()),
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("os.path.exists", return_value=True),
        patch("os.remove", MagicMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await mcp_ai_perform_scanning(mock_event, mock_scheduled_md)

        mock_nuclei.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_ai_perform_scanning_missing_base_url(mock_event, mock_scheduled_md):
    """Test that handler skips when base-url is missing in XML."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_scanning

    mock_app = {
        "id": "app-789",
        "site": "https://scan.example.com",
        "url": "https://scan.example.com",
    }
    xml_content = """<scanning>
<templates>http/cves/test.yaml</templates>
</scanning>"""
    mock_annotation = {"id": "ann-scan", "key": "tool-scanning", "value": xml_content}

    mock_entries = {"ann-scan": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.utils.run_nuclei_scan", AsyncMock()) as mock_nuclei,
    ):
        await mcp_ai_perform_scanning(mock_event, mock_scheduled_md)

        mock_nuclei.assert_not_called()


# =============================================================================
# Tests for mcp_ai_perform_fuzzing
# =============================================================================


@pytest.mark.asyncio
async def test_mcp_ai_perform_fuzzing_happy_path(mock_event, mock_scheduled_md):
    """Test happy path: fuzzing annotation is processed and ffuf scan runs."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_fuzzing

    mock_app = {
        "id": "app-fuzz",
        "site": "https://fuzz.example.com",
        "url": "https://fuzz.example.com",
    }
    xml_content = """<fuzzing>
<base-url>https://fuzz.example.com/api</base-url>
<wordlist>https://raw.githubusercontent.com/example/wordlist.txt</wordlist>
</fuzzing>"""
    mock_annotation = {"id": "ann-fuzz", "key": "tool-fuzzing", "value": xml_content}

    mock_entries = {"ann-fuzz": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_storage = MagicMock()
    mock_storage.add_many = MagicMock()

    mock_file = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_ffuf_scan",
            AsyncMock(return_value=[{"path": "/admin", "status": 200}]),
        ) as mock_ffuf,
        patch(
            "rcn_web.scanning.mcp_scanners.get_storage_create",
            return_value=mock_storage,
        ),
        patch("rcn_web.scanning.mcp_scanners.global_add_annotation", MagicMock()),
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("validators.url", return_value=True),
        patch("os.path.exists", return_value=True),
        patch("os.remove", MagicMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await mcp_ai_perform_fuzzing(mock_event, mock_scheduled_md)

        mock_ffuf.assert_called_once()
        mock_storage.add_many.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_ai_perform_fuzzing_empty_entries(mock_event, mock_scheduled_md):
    """Test that handler returns early when no unprocessed annotations."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_fuzzing

    mock_context = create_mock_context_manager({})

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.utils.run_ffuf_scan", AsyncMock()) as mock_ffuf,
    ):
        await mcp_ai_perform_fuzzing(mock_event, mock_scheduled_md)

        mock_ffuf.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_ai_perform_fuzzing_dynamic_code(mock_event, mock_scheduled_md):
    """Test that dynamic code wordlist generation works correctly."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_fuzzing

    mock_app = {
        "id": "app-fuzz",
        "site": "https://fuzz.example.com",
        "url": "https://fuzz.example.com",
    }
    xml_content = """<fuzzing>
<base-url>https://fuzz.example.com/api</base-url>
<dynamic-code>
def generate_wordlist():
    return ['admin', 'backup', 'config']
</dynamic-code>
</fuzzing>"""
    mock_annotation = {"id": "ann-fuzz", "key": "tool-fuzzing", "value": xml_content}

    mock_entries = {"ann-fuzz": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_storage = MagicMock()
    mock_storage.add_many = MagicMock()
    mock_file = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_ffuf_scan", AsyncMock(return_value=[])
        ) as mock_ffuf,
        patch(
            "rcn_web.scanning.mcp_scanners.get_storage_create",
            return_value=mock_storage,
        ),
        patch("rcn_web.scanning.mcp_scanners.global_add_annotation", MagicMock()),
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("validators.url", return_value=False),
        patch("os.path.exists", return_value=True),
        patch("os.remove", MagicMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await mcp_ai_perform_fuzzing(mock_event, mock_scheduled_md)

        mock_ffuf.assert_called_once()
        call_args = mock_ffuf.call_args
        wordlists = call_args[0][1]
        assert any("gen_wordlist" in w for w in wordlists)


@pytest.mark.asyncio
async def test_mcp_ai_perform_fuzzing_no_wordlists(mock_event, mock_scheduled_md):
    """Test that handler skips when no wordlists are available."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_fuzzing

    mock_app = {
        "id": "app-fuzz",
        "site": "https://fuzz.example.com",
        "url": "https://fuzz.example.com",
    }
    xml_content = """<fuzzing>
<base-url>https://fuzz.example.com/api</base-url>
</fuzzing>"""
    mock_annotation = {"id": "ann-fuzz", "key": "tool-fuzzing", "value": xml_content}

    mock_entries = {"ann-fuzz": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_file = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch("rcn_web.scanning.utils.run_ffuf_scan", AsyncMock()) as mock_ffuf,
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("os.path.exists", return_value=True),
        patch("os.remove", MagicMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await mcp_ai_perform_fuzzing(mock_event, mock_scheduled_md)

        mock_ffuf.assert_not_called()


@pytest.mark.asyncio
async def test_mcp_ai_perform_fuzzing_error_path(mock_event, mock_scheduled_md):
    """Test error path: exception during fuzzing is handled gracefully."""
    from rcn_web.scanning.mcp_scanners import mcp_ai_perform_fuzzing

    mock_app = {
        "id": "app-fuzz",
        "site": "https://fuzz.example.com",
        "url": "https://fuzz.example.com",
    }
    xml_content = """<fuzzing>
<base-url>https://fuzz.example.com/api</base-url>
<wordlist>https://example.com/wordlist.txt</wordlist>
</fuzzing>"""
    mock_annotation = {"id": "ann-fuzz", "key": "tool-fuzzing", "value": xml_content}

    mock_entries = {"ann-fuzz": {"entry": mock_annotation, "parent": mock_app}}
    mock_context = create_mock_context_manager(mock_entries)

    mock_file = AsyncMock()

    with (
        patch(
            "rcn_web.scanning.mcp_scanners.get_unprocessed_annotations",
            return_value=mock_context,
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.web_match_storage",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "rcn_web.scanning.utils.run_ffuf_scan",
            AsyncMock(side_effect=RuntimeError("Ffuf failed")),
        ),
        patch(
            "rcn_web.scanning.mcp_scanners.global_add_annotation", MagicMock()
        ) as mock_add_ann,
        patch("aiofiles.open") as mock_aiofiles_open,
        patch("validators.url", return_value=True),
        patch("os.path.exists", return_value=True),
        patch("os.remove", MagicMock()),
    ):
        mock_aiofiles_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
        mock_aiofiles_open.return_value.__aexit__ = AsyncMock(return_value=None)

        await mcp_ai_perform_fuzzing(mock_event, mock_scheduled_md)

        mock_add_ann.assert_called()
