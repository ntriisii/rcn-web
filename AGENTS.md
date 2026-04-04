# PROJECT KNOWLEDGE BASE

**Generated:** Mon Mar 23 2026
**Commit:** 03267e1
**Branch:** master

## OVERVIEW
rcn-web is a web reconnaissance and scanning platform built on FastAPI and Mitmproxy. It orchestrates target discovery, application scanning, and data storage using a hierarchical SQLite-based system (rcn-core).

## STRUCTURE
```
rcn-web/
├── rcn_web/              # Main Python package
│   ├── core/             # Core logic (scope, events, utilities)
│   ├── routes/           # FastAPI routes (applications, domains, IPs, storage)
│   ├── scanning/         # Scanning modules (app_scans, owasp, client_side, js_analysis)
│   ├── storage/          # Storage handlers (url, fuzzing, ip, js, vuln_scanning)
│   ├── flows/            # Flow collectors (JS, URLs, secrets)
│   ├── viewers/          # Emacs viewers for data display
│   ├── main.py           # FastAPI app entry point
│   └── server_actions.py # Server-side actions
├── server.py             # Mitmproxy reverse proxy server (port 8030)
├── mcp_server.py         # MCP protocol server
└── pyproject.toml        # Project metadata with rcn-core dependency
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Target Discovery | `rcn_web/scanning/app_scans.py` | Main logic for discovery and tech detection |
| Scope Management | `rcn_web/core/scope.py` | Wildcard and URL scope validation |
| API Endpoints | `rcn_web/routes/` | FastAPI routers for apps, IPs, and storage |
| Storage Handlers | `rcn_web/storage/` | Hierarchical storage logic (e.g., `web-apps::*`) |
| Event Handlers | `rcn_web/core/events.py` | `@rcn_event()` decorated async functions |

## CODE MAP
| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `rcn_web.core.utils` | Module | `rcn_web/core/utils.py` | Central hub for storage access and app CRUD |
| `rcn_web.core.scope` | Module | `rcn_web/core/scope.py` | Scope validation and target configuration |
| `@rcn_event()` | Decorator | `rcn_core.decorators` | Marks scheduled async functions (must have 2 params) |
| `TargetStorage` | Class | `rcn_core.storage` | Target-level storage management |

## CONVENTIONS
- **Scheduled Functions**: MUST use `@rcn_event()` and accept `(event, scheduled_md)`.
- **Storage Naming**: Use `web-apps::*` prefix for application-related data.
- **Async First**: Use `async/await` for all I/O and storage operations.
- **Naming**: `snake_case` for functions/methods, `PascalCase` for classes.

## ANTI-PATTERNS (THIS PROJECT)
- **DO NOT** use `JOIN`, `UNION`, or modification keywords in `sql_filter` parameters.
- **DO NOT** use `find()`, `search()`, or `filter()` on storage objects; use `.get()` and filter in Python.
- **NEVER** use `# :server-url:` metadata in Org-mode; URLs are resolved automatically.
- **NEVER** generate `:PROPERTIES:` blocks manually in Org-mode nodes.
- **DO NOT** execute scanning tools unless explicitly commanded (default is review mode).

## COMMANDS
```bash
# Run main web server
python -m rcn_web <target_dir> --port 8000

# Run mitmproxy reverse proxy
mitmproxy -s server.py

# Run MCP server
python mcp_server.py

# Run tests using the local virtual environment
./.venv/bin/pytest
```

## NOTES
- **Dependency**: Depends on `rcn-core` and `pentest-utils` (local editable packages).
- **Storage**: Uses hierarchical SQLite storage. `web-apps` is the parent for most scanning data.
- **Org-Mode**: Deeply integrated with Emacs/Org-mode for request generation and viewing.
