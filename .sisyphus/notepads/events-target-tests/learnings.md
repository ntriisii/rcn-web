# Learnings for Client-Side Scanning Tests

## Test Patterns for `@rcn_event` Functions

### Mocking `get_unprocessed_entries`
The `get_unprocessed_entries` function is an async context manager. Mock it using:
```python
mock_context = MagicMock()
mock_context.__aenter__ = AsyncMock(return_value=mock_entries)
mock_context.__aexit__ = AsyncMock(return_value=None)

with patch("module.get_unprocessed_entries", return_value=mock_context):
    # test code
```

### Mocking `HeadlessBrowser`
`HeadlessBrowser` is an async context manager with an async `get()` method:
```python
mock_browser = MagicMock()
mock_browser.get = AsyncMock(side_effect=mock_get_function)
mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
mock_browser.__aexit__ = AsyncMock(return_value=None)

with patch("module.HeadlessBrowser", return_value=mock_browser):
    # test code
```

### Key Insight: Query Parameter Fuzzing
When testing `scan_client_side_reflected_content`, the source code:
1. Iterates over each query parameter
2. Generates a unique 8-character alphanumeric probe for EACH parameter
3. Replaces only that parameter's value with the probe (others keep original values)
4. Checks if the probe appears in the response

This means when fuzzing `?q=test&category=all`:
- First iteration: `?q=PROBE1&category=all` (category still has original value)
- Second iteration: `?q=test&category=PROBE2` (q still has original value)

The mock browser must use regex to find the probe value in params, not assume it's always the first param.

### Mocking `global_add_annotation`
Track annotation calls with a side_effect function:
```python
annotation_calls = []

def mock_add_annotation(entry_id, storage_name, key, value, parent_id):
    annotation_calls.append({...})

with patch("module.global_add_annotation", side_effect=mock_add_annotation):
    # test code
```

## Test Coverage
- Happy path: reflection detected for multiple query params
- Empty entries: early return without browser instantiation
- No query params: skips browser.get() calls
- Browser error: exception caught, no annotation added
- Wrong note key: skips processing
- No reflection: no annotation added

## Learnings for Scanning Utils Tests

### Mocking `start_scheduled_process`
The `start_scheduled_process` function is imported inside the handler function from `rcn_core.time_event`. Patch it at the source module:
```python
with patch("rcn_core.time_event.start_scheduled_process", AsyncMock(return_value="")):
    # test code
```

### Mocking `aiohttp.ClientSession`
`aiohttp.ClientSession` is an async context manager, and `session.get()` also returns an async context manager:
```python
mock_response = MagicMock()
mock_response.status = 200
mock_response.text = AsyncMock(return_value="content")

mock_get_context = MagicMock()
mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
mock_get_context.__aexit__ = AsyncMock(return_value=None)

mock_session = MagicMock()
mock_session.get = MagicMock(return_value=mock_get_context)
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=None)

with patch("aiohttp.ClientSession", return_value=mock_session):
    # test code
```

### Source Code Bug: `nuclei_args` Undefined
The `nuclei_scan_apps` function in `rcn_web/scanning/utils.py` references `nuclei_args` which is never defined. Work around this by injecting the attribute at runtime:
```python
import rcn_web.scanning.utils as utils_module
utils_module.nuclei_args = ""
# ... run test ...
delattr(utils_module, "nuclei_args")
```

### Error Propagation in `crawl_application`
The `crawl_application` function uses `try/finally` (not `try/except`), so exceptions propagate but cleanup still happens. Test with:
```python
with pytest.raises(RuntimeError):
    await crawl_application(mock_event, mock_scheduled_md)
mock_remove.assert_called()  # cleanup verified
```

## Learnings for App Scans Tests

### MockApp Class for Hashable Parent Objects
The `ai_annotate_link_entries` handler uses `app` (parent) as a dictionary key in `app_links_mapping`. This requires the parent object to be hashable. Create a `MockApp` class with:
- `__hash__` method (using `id` attribute)
- `__eq__` method for comparison
- `__getitem__` method for subscriptable access (`app['id']`)
- `get` method for dict-like access (`app.get('site')`)

### Source Code Has Hardcoded AI Response
The `ai_annotate_link_entries` function in `app_scans.py` has the actual `ai_ask` call commented out (lines 100-108) and uses a hardcoded response instead. Tests should account for this by not asserting specific annotation values that depend on the AI response matching mock data.

### Storage Mock Pattern
When mocking storage objects, set `storage_name` attribute:
```python
mock_storage = MagicMock()
mock_storage.storage_name = "web-apps::app-links"
```

## Learnings for JS Analysis Tests

### Mocking `RemoteFlowsAdapter`
The `RemoteFlowsAdapter` is a singleton accessed via `get_instance()`. Mock it at the class level:
```python
mock_adapter = MagicMock()
mock_adapter.get_flows_by_id = AsyncMock(return_value=[{"response-body": "content"}])

with patch("module.RemoteFlowsAdapter.get_instance", return_value=mock_adapter):
    # test code
```

### Understanding `js_intelligence_monitor` Flow
The handler has two places where `get_storage_create` is called:
1. **Inside `handle_monitor_js_hash`** (line 99-101): Called to check existing inventory entries via `get_filtered`
2. **In the main loop** (line 59-62): Called only when `inventory_entries` list is non-empty

When testing scenarios where all results are `None` (out of scope, missing URL, unchanged hash, errors):
- The main loop's `get_storage_create` is NOT called (because `inventory_entries` is empty)
- But `handle_monitor_js_hash` still calls `get_storage_create` internally to check existing entries

For "unchanged hash" test: verify `add_many` was NOT called (not that `get_storage_create` wasn't called).

### Storage `add_many` Only Called with Non-Empty List
The pattern `if inventory_entries: js_inventory.add_many(...)` means:
- When all `handle_monitor_js_hash` calls return `None`, `add_many` is never called
- Test should verify `add_many.assert_not_called()` for error/skip scenarios

### Multiple Apps Pattern
When testing multiple apps with multiple JS links, use a factory function for `get_storage_create`:
```python
storage_creates = {}

def mock_get_storage_create_fn(name, parent_id):
    if parent_id not in storage_creates:
        storage_creates[parent_id] = MagicMock()
        storage_creates[parent_id].add_many = MagicMock()
        storage_creates[parent_id].get_filtered = MagicMock(return_value=[])
    return storage_creates[parent_id]

with patch("module.get_storage_create", side_effect=mock_get_storage_create_fn):
    # test code

# Verify each app's storage was called
assert "app-id-1" in storage_creates
storage_creates["app-id-1"].add_many.assert_called_once()
```
