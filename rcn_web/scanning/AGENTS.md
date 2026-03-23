# SCANNING KNOWLEDGE BASE

## OVERVIEW
The `scanning` package handles automated and AI-assisted reconnaissance, vulnerability detection, and security analysis. It integrates with external tools (Nuclei, Ffuf, Katana) and uses AI for intelligent tagging and custom template generation.

## STRUCTURE
```
rcn_web/scanning/
├── app_scans.py      # Main entry point for target discovery and AI annotation
├── mcp_scanners.py   # AI integration for Nuclei/Fuzzing tagging and generation
├── owasp.py          # Specialized scanners for common web vulnerabilities
├── js_analysis.py    # JS file monitoring and security analysis (Semgrep, Jsluice)
├── client_side.py    # Headless browser-based client-side reflection scanning
└── utils.py          # Shared utilities for Nuclei, Ffuf, and Katana execution
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Target Discovery | `app_scans.py` | AI-driven annotation of potential vulnerabilities in links |
| AI Tagging | `mcp_scanners.py` | XML-based instructions for Nuclei and Fuzzing tasks |
| Vulnerability Scans | `owasp.py` | Logic for XSS, SQLi, RCE, SSRF, and CSRF detection |
| JS Security | `js_analysis.py` | Hash monitoring and pipeline for JS vulnerability analysis |
| Fuzzing Logic | `utils.py` | Implementation of `run_ffuf_scan` and result processing |

## CODE MAP
| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `ai_annotate_link_entries` | Function | `app_scans.py` | Uses AI to tag links with potential vulnerability types |
| `mcp_ai_tag_apps_for_scanning` | Function | `mcp_scanners.py` | Generates XML instructions for Nuclei/Fuzzing |
| `scan_client_side_reflected_content` | Function | `client_side.py` | Fuzzes query params to detect reflected content |
| `run_nuclei_scan` | Function | `utils.py` | Wrapper for executing Nuclei with custom templates |
| `js_intelligence_monitor` | Function | `js_analysis.py` | Tracks JS file changes via hash comparison |

## CONVENTIONS
- **AI Integration**: Use XML tags (`<scanning>`, `<fuzzing>`) for AI-generated instructions.
- **Event Decorators**: All scheduled scanning tasks MUST use `@rcn_event()`.
- **Storage**: Scanning results should be stored in `web-apps::*` sub-storages (e.g., `nuclei-scanning`, `fuzzing-data`).
- **Temporary Files**: Use `/tmp/` for intermediate target lists or wordlists, and ensure cleanup.

## ANTI-PATTERNS
- **DO NOT** run heavy scans (Nuclei/Ffuf) without checking `unprocessed_entries`.
- **DO NOT** hardcode wordlist paths; use `wordlists/` project root or remote URLs.
- **NEVER** block the event loop with synchronous subprocess calls; use `start_scheduled_process`.

## COMMANDS
```bash
# Run Nuclei scan via rr wrapper
rr nuclei -l targets.txt -t templates/

# Run Ffuf fuzzing via rr wrapper
rr ffuf -u https://target.com/FUZZ -w wordlist.txt
```

## NOTES
- **AI Tagging**: AI can generate custom Nuclei templates and dynamic Python wordlist generators.
- **JS Analysis**: Uses `RemoteFlowsAdapter` to retrieve JS content from captured traffic.
- **Reflected Content**: `client_side.py` uses a headless browser for accurate reflection detection.
