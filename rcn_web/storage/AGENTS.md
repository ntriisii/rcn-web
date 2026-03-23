# STORAGE ARCHITECTURE

## OVERVIEW
The storage layer in `rcn-web` manages hierarchical data using `rcn-core`. It organizes reconnaissance data by target and application, using a structured naming convention and specialized handlers for different data types.

## STRUCTURE
```
rcn_web/storage/
├── domains.py          # Subdomain discovery and passive enumeration
├── fuzzing/            # Fuzzing result storage (paths, status codes)
├── ip/                 # IP/ASN intelligence (Shodan, Censys, Whois)
├── js/                 # JavaScript file storage and analysis (jsluice)
├── url/                # URL management and similarity deduplication
├── vuln_scanning/      # Vulnerability scan results (Nuclei)
├── secrets.py          # Secret discovery storage
└── utils.py            # Storage access wrappers
```

## WHERE TO LOOK
| Data Type | Location | Notes |
|-----------|----------|-------|
| Subdomains | `domains.py` | Handles passive recon and bruteforcing |
| IP Intel | `ip/ip.py` | Shodan/Censys integration and ASN tracking |
| URL Similarity | `url/url_sim_algo.py` | Deduplication logic for crawled URLs |
| JS Analysis | `js/js.py` | Local JS storage and jsluice analysis |
| Vuln Data | `vuln_scanning/utils.py` | Nuclei result mapping to apps/URLs |

## CODE MAP
| Symbol | Type | Role |
|--------|------|------|
| `get_storage_create` | Function | Primary way to obtain/initialize storage objects |
| `web-apps::*` | Prefix | Namespace for application-level storage |
| `url_sim_algo` | Module | Implements URL pattern matching for deduplication |
| `handle_unprocessed_ips` | Async Fn | Processes new IPs through Shodan/Censys flows |

## CONVENTIONS
- **Hierarchical Naming**: Use `web-apps::[type]` for app-specific data.
- **Parent Linking**: Always provide `parent_id=app['id']` for app-related storage.
- **Deduplication**: Use `url_sim_algo` before adding new URLs to prevent bloat.
- **Async Processing**: Use `@rcn_event` for handlers processing "unprocessed" entries.

## ANTI-PATTERNS
- **DO NOT** use raw SQLite queries; use `rcn-core` storage abstractions.
- **DO NOT** store large binary files in SQLite; use local filesystem (e.g., `js/` directory).
- **NEVER** bypass `get_storage_create` when initializing new storage namespaces.

## NOTES
- **IP Intelligence**: Depends on external API keys (Shodan, Censys) configured in the environment.
- **URL Similarity**: The algorithm uses bitwise patterns to represent URL structures.
