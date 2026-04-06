---
name: rcn-debug-map
description: Deep dive into the architecture of pentest-utils, rcn-core, and rcn-web.
---

# RCN Debug Map
Deep dive into the architecture of `pentest-utils`, `rcn-core`, and `rcn-web`.

## PACKAGE RESPONSIBILITIES
| Package | Role | Key Files |
|---------|------|-----------|
| `rcn-web` | Orchestration & API | `server.py`, `rcn_web/routes/mcp_api.py` |
| `rcn-core` | Storage & Events | `rcn_core/storage/bases.py`, `rcn_core/mcp/api.py` |
| `pentest-utils`| Base Utils & AST | `pentest_utils/storage/shared.py`, `pentest_utils/viewers/emacs/match_groups.py` |

## DEBUGGING STRATEGIES

### 1. The Filter AST Pipeline
When a filter like `entry['id'] == 123` is sent:
1. `rcn_web/routes/mcp_api.py`: Receives request, resolves storage.
2. `rcn_core/mcp/utils.py`: Calls `parse_filter_to_querynode`.
3. `pentest_utils/viewers/emacs/match_groups.py`: `eval()`s string into `QueryNode` AST.
4. `rcn_core/storage/bases.py`: `get_view_data` calls `st.compile_query(node)`.
5. `pentest_utils/storage/shared.py`: `compile_query` generates SQL string and params.

### 2. Testing with Scripts
Always create a standalone reproduction script to avoid proxy/network overhead.
```python
import sys, os
# FORCE LOCAL SOURCES
sys.path.insert(0, os.path.expanduser("~/programming-projects/python/rcn-core/"))
sys.path.insert(0, os.path.expanduser("~/programming-projects/python/pentest-utils/"))

import rcn_core.globals
from rcn_core.storage.target_storage import MultiTargetStorage

# Initialize storage context
ts = MultiTargetStorage("/home/ahmed/recon/new-target/")
rcn_core.globals.TARGET_STORAGE = ts

# Test a specific component
st = ts.get_storage_create("web-apps")
from pentest_utils.viewers.emacs.match_groups import parse_rule_to_node
node = parse_rule_to_node("entry['id'] == 123")
print(st.compile_query(node))
```

### 3. Debugging SQL Issues
- **Ambiguous Columns**: Occurs when a JOIN is used. Check `_get_view_query_parts` in `bases.py`.
- **Type Mismatches**: IDs are often integers. Ensure your script tests both `123` and `'123'`.
- **Database Locks**: If testing against a live target, use `timeout=60.0` in `sqlite3.connect`.

## SOURCE CODE LOCATIONS
- `pentest-utils`: `~/programming-projects/python/pentest-utils/`
- `rcn-core`: `~/programming-projects/python/rcn-core/`
- `rcn-web`: `~/programming-projects/python/rcn-web/`
