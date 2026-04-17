---
name: rcn-target-ops
description: Detailed workflows for managing, restarting, and troubleshooting running RCN targets.
---

# RCN Target Operations

## 1. INFRASTRUCTURE OVERVIEW
The system operates as a **Proxy -> Downstream** architecture:
- **Proxy Server (`server.py`)**: Runs on port `8023`. It is the entry point for the Elisp frontend. It routes requests to the correct target by spawning/managing downstream `rcn_web` instances.
- **Downstream Instances (`rcn_web`)**: Run on ports `8031+`. Each instance is tied to a specific `<target_dir>`.

### Crucial Files
- `server.py`: Proxy logic, process management, and `STARTUP_LOCK` to prevent race conditions.
- `rcn_web/main.py`: The FastAPI application entry point for downstream targets.
- `rcn_web/__main__.py`: CLI entry point for the `python -m rcn_web` command.

---

## 2. WORKFLOW: STARTING & RESTARTING

### Automatic (Recommended)
Simply access the target via the Elisp UI or a URL like `http://localhost:8023/<target-name>/...`. The proxy will:
1. Identify the target from the path.
2. Check if a process is already running on a assigned port.
3. If not, spawn a new `python -m rcn_web` process.

### Manual Restart (Development/Debugging)
If you've made code changes in `rcn-web` or `rcn-core`, you MUST restart the target to see the effect:
```bash
# Force a reload via the proxy
curl -X POST http://localhost:8023/restartTarget/<target-name>
```

---

## 3. WORKFLOW: TROUBLESHOOTING

### Symptom: 502 Bad Gateway (Proxy)
**Cause**: The downstream `rcn_web` instance failed to start or crashed.
**Action**:
1. Check for zombie processes: `ps aux | grep rcn_web`.
2. Kill them: `pkill -f rcn_web`.
3. Check the target directory: Ensure `rcn_automation_data.db` exists and is writable.
4. Try starting manually to see the error:
   `./.venv/bin/python -m rcn_web /path/to/target/ --port 8031`

### Symptom: 404 Not Found (MCP Storage)
**Cause**: The storage name is incorrect, or the `parent_id` (Target ID) doesn't match the database.
**Action**:
1. Verify the storage exists: `sqlite3 <target_dir>/rcn_automation_data.db ".tables"`.
2. Check the Target ID: `sqlite3 <target_dir>/rcn_automation_data.db "SELECT id FROM targets"`.
3. Verify the resolution logic in `rcn_web/routes/mcp_api.py`.

### Symptom: Filter Returns No Data
**Cause**: Ambiguous column names in JOINs or ID type mismatches.
**Action**:
1. Check if the storage uses a JOIN in `_get_view_query_parts()` (in `rcn_core/storage/bases.py`).
2. If it does, ensure the filter uses the `main.` prefix for `id` or `timestamp`.
3. Use a reproduction script (see `rcn-debug-map` skill) to capture the exact SQL error.

### Symptom: Events Not Running
**Cause**: The event loop is stuck or the `@rcn_event` decorator failed to register.
**Action**:
1. Check `rcn_web/core/events.py` for errors.
2. Ensure the function signature is `async def name(event, scheduled_md)`.
3. Verify `rcn_automation_data.db` table `delayed_operations` for pending tasks.

---

## 4. DATA FORMAT CONVENTIONS

### Content Negotiation (Accept Header)
The MCP endpoint `/mcp/view` supports content negotiation via the `Accept` header to provide raw data for automation:

| Endpoint | Accept Header | Output Format | Description |
|----------|---------------|---------------|-------------|
| `/view` | `application/json` | **JSONL (Data)** | Returns raw entries as JSON Lines (one object per line). |
| `/view` | *None / text/plain* | **Text (Formatted)** | Returns human-readable text optimized for LLM consumption. |
| `/preview`| (Any) | **Text (Formatted)** | Always returns human-readable summary/metadata as text. |

### CLI Usage
The `rcn-web-interact` CLI tool handles formatting for downstream piping:
- `rcn-web-interact <target> preview --storage <name>`: Prints human-readable text preview.
- `rcn-web-interact <target> view --storage <name>`: Prints raw JSONL data (requests `application/json`).
