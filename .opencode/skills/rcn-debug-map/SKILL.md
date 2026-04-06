---
name: rcn-debug-map
description: Workflow and relationship map for debugging rcn-web, rcn-core, and pentest-utils.
---

# RCN Debug Map

## 1. PROJECT DEPENDENCIES & RELATIONSHIPS
An error in `rcn-web` often stems from its underlying local libraries:
- **`rcn-web` (Orchestration)**: FastAPI, proxy, routes, scanning events.
- **`rcn-core` (Foundational Logic)**: Base classes for storage, generic MCP API, event system, and SQLite schema management.
- **`pentest-utils` (Core Utilities)**: Low-level SQL compilers, filter AST parsing, and shared data structures.

### Development Workflow
When making changes, you must ensure you are editing the **local source code** and not the installed site-packages.
1. Force local imports by inserting project paths into `sys.path`.
2. Reload modified modules using `importlib.reload`.
3. Restart the `rcn_web` target (see `rcn-target-ops` skill).

---

## 2. WORKFLOW: DEBUGGING STORAGES
### The "Ambiguous Column" Issue
**Context**: Many storages (e.g., `web-apps`) use JOINs with a `main.` alias.
**Action**:
- If `entry['id']` is failing, check if the SQL compiler in `pentest-utils` correctly prefixes the column with `main.`.
- Verify the `get_view_data` method in `rcn_core/storage/bases.py` for correct SQL assembly.

### Hierarchical Resolution
**Context**: Sub-storages like `web-apps::app-flows` must resolve correctly.
**Action**:
- Check `rcn_web/routes/mcp_api.py` function `_resolve_storage`.
- Ensure `web_match_storage` in `rcn_web/core/utils.py` correctly identifies the hierarchical pattern.

---

## 3. WORKFLOW: DEBUGGING EVENTS
### Registration & Scheduling
**Context**: Tasks like `@rcn_event() async def handle_init_target` must be discovered.
**Action**:
- Check `rcn_web/core/events.py` for event registration logic.
- Verify the `delayed_operations` table in the target's `.db` file for pending tasks.

---

## 4. REPRODUCTION SCRIPT TEMPLATE
Use this script to isolate issues without proxy/network interference.
```python
import sys, os, importlib

# 1. FORCE LOCAL SOURCES
core_path = os.path.expanduser("~/programming-projects/python/rcn-core/")
utils_path = os.path.expanduser("~/programming-projects/python/pentest-utils/")
sys.path.insert(0, core_path)
sys.path.insert(0, utils_path)

# 2. RELOAD MODIFIED MODULES
import rcn_core.storage.bases
importlib.reload(rcn_core.storage.bases)
from rcn_core.storage.target_storage import MultiTargetStorage

# 3. INITIALIZE CONTEXT
# Use a real target directory with existing data
ts = MultiTargetStorage("/home/ahmed/recon/new-target/")
import rcn_core.globals
rcn_core.globals.TARGET_STORAGE = ts

# 4. TEST STORAGE RESOLUTION
from rcn_web.routes.mcp_api import _resolve_storage
st = _resolve_storage("web-apps", 2668751585)

# 5. TEST FILTERS
from pentest_utils.viewers.emacs.match_groups import parse_rule_to_node
node = parse_rule_to_node("entry['id'] == 17525774")
try:
    items = st.get_view_data(query_node=node, limit=1)
    print(f"Items: {len(items)}")
except Exception as e:
    print(f"ERROR: {e}")
```

---

## 5. SOURCE CODE REFERENCE
- `pentest-utils`: `pentest_utils/storage/shared.py` (SQL Compiler)
- `rcn-core`: `rcn_core/storage/bases.py` (AbstractDataStorage), `rcn_core/mcp/api.py` (MCP Router)
- `rcn-web`: `rcn_web/routes/mcp_api.py` (Storage Resolver), `rcn_web/main.py` (App Root)
