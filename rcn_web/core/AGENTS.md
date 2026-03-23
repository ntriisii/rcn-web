# RCN-WEB CORE KNOWLEDGE BASE

## OVERVIEW
Foundational logic for scope validation, event orchestration, and storage utilities. Bridges `rcn-core` with web-specific scanning requirements.

## COMPONENTS

### Scope Management (`scope.py`)
- **Wildcard/URL Validation**: Handles target scope configuration and matching.
- **`get_target_scope`**: Retrieves scope from target YAML.
- **`flow_in_scope`**: Validates MITM flows against target boundaries.

### Event Orchestration (`events.py`)
- **Scheduled Tasks**: Uses `@rcn_event()` for async background processing.
- **`handle_init_target`**: Orchestrates initial recon and domain discovery.
- **Integration**: Uses `web_match_storage` for application-aware entry processing.

### Central Utilities (`utils.py`)
- **Storage Hub**: Centralized CRUD for web applications (`get_app_by_site`, `add_apps`).
- **`web_match_storage`**: Custom matcher for `web-apps::*` and `flows` storage patterns.
- **`RemoteFlowsAdapter`**: Singleton adapter fetching MITM flows from `localhost:8082`.
- **`get_uniq_apps`**: Filters unique, in-scope applications for scanning events.

### Flow Processing (`remote_flow_processor.py`)
- **Secret Scanning**: `trufflehog_check_for_flow_secrets` identifies leaked credentials.
- **JS Extraction**: `collect_js_files` harvests scripts for analysis.
- **URL Collection**: `collect_in_scope_urls` aggregates discovered endpoints.

## CONVENTIONS
- **Events**: Functions MUST use `@rcn_event()` and accept `(event, scheduled_md)`.
- **Flows**: Access MITM data via `web_match_storage("flows")`.
- **App Context**: Use `web_match_storage("web-apps::[sub-storage]")` for per-app data.
- **Scope**: Always verify `flow_in_scope()` before processing external traffic.

## MITM INTEGRATION
- `RemoteFlowsAdapter` bridges the MITM proxy to the event system.
- Implements `get_unprocessed_entries` for live traffic processing.
- Uses flow `timestamp` as the unique identifier for pagination.
