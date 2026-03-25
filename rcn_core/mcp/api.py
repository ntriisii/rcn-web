"""Dummy MCP API module for testing purposes.
Provides placeholder functions that are patched in tests.
"""


def preview_storage(*args, **kwargs):
    """Placeholder for preview_storage function.
    Returns None; tests will patch this.
    """
    return None


def view_storage(*args, **kwargs):
    """Placeholder for view_storage function.
    Returns None; tests will patch this.
    """
    return None


def execute_action(*args, **kwargs):
    """Placeholder for execute_action function.
    Returns None; tests will patch this.
    """
    return None
