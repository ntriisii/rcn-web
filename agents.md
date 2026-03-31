# JavaScript Analysis Memory

## Events
- **`collect_js_files`** (`rcn_web/core/remote_flow_processor.py`):
    - Decorator: `@rcn_event()`
    - Logic: Processes proxy flows, identifies JS content using `extract_js_files`.
    - Action: Calls `handle_collected_js_files` which runs `jsluice` to extract links and secrets.
    - Storage: Populates `web-apps::js-flows` and `web-apps::js-secrets`.

- **`js_intelligence_monitor`** (`rcn_web/scanning/js_analysis.py`):
    - Decorator: `@rcn_event()`
    - Config: `require-storage: web-apps::js-flows`
    - Logic: Monitors `js-flows` for new JS file URLs.
    - Action: Fetches content, tracks SHA-256 hashes in `js-inventory`, and triggers the deep analysis pipeline (`process_js_file`).
    - AI: Delegates findings to AI agents via `targets::annotations` with key `js-analyst`.

## Storages
- **`web-apps::js-flows`**: High-level references to JS files seen during live proxying and URLs extracted from JavaScript files by `jsluice`.
- **`web-apps::js-inventory`**: Tracks JS file URLs, their content hashes, and analysis status.
- **`web-apps::js-intelligence`**: Stores JSON-formatted findings from Semgrep, jsluice, ppmap, and Nuclei.
- **`web-apps::js-analysis`**: (Legacy/Secondary) Stores raw `jsluice` output in some workflows.

