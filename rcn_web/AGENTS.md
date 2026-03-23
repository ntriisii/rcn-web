# RCN-WEB PACKAGE KNOWLEDGE BASE

## OVERVIEW
`rcn_web` is the FastAPI-based orchestration layer for the RCN platform. It provides a web API, scheduled scanning events, and data visualization for Emacs, wrapping the underlying `rcn-core` storage and event system.

## STRUCTURE
```
rcn_web/
├── core/             # Scope validation, events, and central utilities
├── routes/           # FastAPI routers (apps, domains, IPs, storage, MCP)
├── scanning/         # Scanning modules with @rcn_event handlers
├── storage/          # Web-specific storage handlers and adapters
├── flows/            # Request/response flow collection and processing
├── viewers/          # Elisp generators for Emacs data visualization
├── main.py           # FastAPI app initialization and route registration
└── __main__.py       # CLI entry point and server startup logic
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| App Initialization | `rcn_web/main.py` | FastAPI setup and lifespan events |
| CLI Entry Point | `rcn_web/__main__.py` | Config loading and uvicorn startup |
| App CRUD/Utils | `rcn_web/core/utils.py` | Central hub for app and storage access |
| Scope Logic | `rcn_web/core/scope.py` | Wildcard and URL scope validation |
| Route Definitions | `rcn_web/routes/` | Entity-specific FastAPI routers |

## CODE MAP
| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `app` | `FastAPI` | `rcn_web/main.py` | Main FastAPI application instance |
| `web_match_storage` | `Function` | `rcn_web/core/utils.py` | Custom storage matcher for web-apps and flows |
| `get_uniq_apps` | `Function` | `rcn_web/core/utils.py` | Retrieves unique in-scope applications |
| `get_target_scope` | `Function` | `rcn_web/core/scope.py` | Retrieves configured scope for the target |

## CONVENTIONS
- **Storage Matching**: Use `web_match_storage` for events targeting web-apps.
- **Route Registration**: Add new routers to `rcn_web/routes/` and include in `main.py`.
- **Scanning**: Implement scanning logic as `@rcn_event` decorated functions.
- **Async**: Use `async/await` for all I/O and storage operations.

## ANTI-PATTERNS
- **DO NOT** initialize storage directly; use `rcn_core.globals.TARGET_STORAGE`.
- **AVOID** circular imports between sub-packages; use late imports if needed.
- **DO NOT** bypass `web_match_storage` when iterating over applications in events.

## COMMANDS
```bash
# Start the web server for a specific target
python -m rcn_web <target_dir> --port 8023
```

## NOTES
- Depends on `rcn-core` and `pentest-utils`.
- Integrates deeply with Emacs via the `viewers/` package for data display.
