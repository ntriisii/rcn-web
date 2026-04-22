---
name: rcn-web-interact
description: Use when the user needs to browse discovered recon assets, explore hierarchical reconnaissance data, or orchestrate automated security scans on the RCN Web platform.
---

# RCN Web Reconnaissance Platform

This skill provides complete control over the RCN Web reconnaissance and scanning platform for systematic target management, data exploration, and automated security testing.

## Server Information

The RCN Web platform provides a command-line interface for all interactions. Use only the provided tools and commands—do not attempt to connect directly to any server URLs.

## Storage Hierarchy

Storages use `::` as a hierarchical separator. Always use `rcn-web-interact <target_name> describe-target` once you start any work to discover available storages and their schemas dynamically.


## Primary Interface: rcn-web-interact

The main CLI tool is `rcn-web-interact`. Use this for ALL server interactions. Note that this tool is for **data management and interaction**; for tool execution, use the `rr` command (see `rr-ops` skill).

### Arguments

- `TARGET`: Target name. This is a mandatory positional argument used to route requests to the target-specific service.

### Command Reference

#### Describe Target (Initial Setup)

**Describe the target and list all available storages:**
```bash
rcn-web-interact <target_name> describe-target
```

This command should be run FIRST when starting work. It returns:
- Target metadata (ID, Site)
- List of all available storages with entry counts
- Sample of columns available in each storage

The target_name is the current directory name you're in ie `~/recon/<target_name>`.

#### Storage Preview (Metadata)

**Preview storage before viewing (use to check available columns):**
```bash
rcn-web-interact <target_name> preview --storage <storage_name> [--filter "<filter>"] [--app-id <id>]
```

Examples:
```bash
# Preview web-apps storage (list all applications)
rcn-web-interact my_target preview --storage "web-apps"

# Preview with filter (use (entry['<column>'] == value) syntax)
rcn-web-interact <target_name> preview --storage "web-apps" --filter "(entry['status_code'] == 200)"

# Preview app-specific sub-storage
rcn-web-interact <target_name> preview --storage "web-apps::js-flows" --app-id 123
```

**Preview shows:**
- Storage name and summary
- Item count
- Available columns/schema
- First 5 entries (human-readable format)

#### Storage View (Actual Data)

**View entries in any storage:**
```bash
rcn-web-interact <target_name> view --storage <storage_name> [--filter "<filter>"] [--page <n>] [--limit <m>] [--sort-by <field>] [--sort-order asc|desc]
```

Examples:
```bash
# View all applications (JSON array output)
rcn-web-interact <target_name> view --storage "web-apps"

# View with limit and pagination
rcn-web-interact <target_name> view --storage "web-apps" --limit 100 --page 2

# View applications sorted
rcn-web-interact <target_name> view --storage "web-apps" --sort-by "status_code" --sort-order desc

# Filter for specific patterns using bitwise logic
rcn-web-interact <target_name> view --storage "web-apps::js-flows" --filter "entry['url'].contains('api/v1')"

# Complex filter (Note REQUIRED parentheses)
rcn-web-interact <target_name> view --storage "web-apps::app-links" --filter "(entry['status'] == 403) & (entry['path'].contains('admin'))"
```

#### Storage CRUD Operations

**Add new entries to a storage:**
```bash
rcn-web-interact <target_name> storage add --name <storage_name> --data '<json_data>' [--app-id <id>]
```
- Example: `rcn-web-interact my_target storage add --name "domains" --data '{"domain": "api.example.com", "source": "manual"}'`

**Update existing entries matching a filter:**
```bash
rcn-web-interact <target_name> storage update --name <storage_name> --filter "<filter>" --updates '<json_data>' [--app-id <id>]
```
- Example: `rcn-web-interact my_target storage update --name "web-apps" --filter "(entry['site'] == 'old.site')" --updates '{"site": "new.site"}'`

**Delete entries from storage matching a filter:**
```bash
rcn-web-interact <target_name> storage delete --name <storage_name> --filter "<filter>" [--app-id <id>]
```
- Example: `rcn-web-interact my_target storage delete --name "web-apps" --filter "(entry['status_code'] == 404)"`

#### Annotations System

Every annotation requires: **Category**, **Key**, and **Value**.

**Add an annotation to an entry:**
```bash
rcn-web-interact <target_name> annotate --storage <storage> --entry-id <id> --category <cat> --key <key> --value <val>
```

**Standard Categories:**

| Category | Purpose | Example Keys | Example Values |
|----------|---------|--------------|----------------|
| `potential-vuln` | Mark potential vulnerabilities | `sqli`, `xss`, `idor`, `ssrf` | Description of the vulnerability |
| `finding` | Document confirmed findings | `api-key`, `secret`, `endpoint` | Found hardcoded key in file.js |
| `notes` | General observations | `interesting`, `suspicious`, `check-later` | Notes about the entry |
| `todo` | Task tracking | `scan`, `analyze`, `verify` | Task description |
| `acp-agent-do` | Delegate to ACP agent | `<agent-name>` | Instructions for the agent |
| `notify` | User notifications | `alert`, `info` | Notification message |

**Example:**
```bash
rcn-web-interact <target_name> annotate --storage "web-apps" --entry-id 123 --category "finding" --key "api-key" --value "Found AWS key in main.js"
```

#### Running Security Tools with rr

The `rr` command distributes scanning tasks across workers. It runs tools like nuclei, ffuf, and dalfox, etc with chunked wordlists for parallel execution.

**Basic rr syntax:**
```bash
rr <program> <args>
```

**Chunk notation for distribution:**
- `:l1`, `:l2` - List chunks for URLs/wordlists
- `:p1`, `:p2` - Port chunks

**Running Nuclei:**
```bash
# Scan targets with nuclei templates
rr nuclei -u https://example.com/ -t http/exposed-panels/:l1

# Scan multiple URLs from file
rr nuclei -l /path/to/urls.txt:l1 -t http/cves/:l1
```

nuclei-templates are in `/home/ahmed/AllForOne/Templates/`

**Running FFUF:**
```bash
# Fuzz with wordlist distribution
rr ffuf -u https://example.com/FUZZ:FUZZ -w ~/wordlists/common.txt:l1
```

#### MCP Actions and Prompts

- **List tools/prompts**: `rcn-web-interact <target> list-tools` or `list-prompts`
- **Execute Action**: `rcn-web-interact <target> action --name <name> [--params '<json>']`
- **Execute Prompt**: `rcn-web-interact <target> prompt --name <name> [--args '<json>']`

## Filter Syntax (CRITICAL)

The system translates Python-style expressions to SQL.

1. **ALWAYS** use parentheses around conditions: `(entry['column'] == value)`
2. **ALWAYS** use bitwise operators for logic: `&` (AND), `|` (OR). Do **NOT** use `and`/`or`.
3. **ALWAYS** use helper methods for string/list matching:
   - Substring: `entry['url'].contains('api')`
   - Membership: `entry['status'].in_([200, 201])`

Example: `--filter "(entry['status_code'] == 200) & (entry['url'].contains('api'))"`

## Advanced Command Patterns

The output of `rcn-web-interact view` is a JSON list. Use `jq` for filtering/extraction or `jsonl-to-entries` for human-readable compact views.

### jsonl-to-entries (Recommended for context saving)

Use `jsonl-to-entries` to convert JSONL data into compact ##-separated entry blocks. This saves context tokens compared to raw JSON output. Pipe the JSON list output from `view` through `jq` to convert to JSONL first:

```bash
rcn-web-interact <target_name> view --storage "web-apps" | jq -c '.[]' | jsonl-to-entries
```

**Examples:**
```bash
# View specific fields only (saves tokens)
rcn-web-interact <target_name> view --storage "web-apps" | jq -c '.[] | {site, url, status_code}' | jsonl-to-entries
```

### JQ Integration Examples

**Get applications and extract URLs:**
```bash
rcn-web-interact view --storage "web-apps" | jq -r '.[].url'
```

**Extract links and format for testing:**
```bash
rcn-web-interact view --storage "web-apps::app-links" --filter "(entry['site'] == 'example.com')" | jq -r '.[] | "\(.status) \(.url)"' | sort -n
```

## Scripting and Automation

### Python Integration

You can use the skill `rcn-scheduled-events` to create automated scanning or analysis logic. When working with scheduled functions (use `@rcn_event` decorator):

```python
from rcn_core.decorators import rcn_event
from rcn_core.data_access import get_unprocessed_entries
from rcn_web.core.utils import web_match_storage

@rcn_event()
async def analyze_new_links(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unprocessed:
        if not unprocessed:
            return
        for item_id, item_data in unprocessed.items():
            entry = item_data['entry']
            url = entry.get('url')
            # Process the entry
            print(f"New link: {url}")
```

## Best Practices

1. **Describe First**: Use `describe-target` to find dynamic storages and schemas once you start working.
2. **Remote Execution**: Always run scanning/fuzzing tools through `rr` (see `rr-ops` skill).
3. **Manual Ingestion**: Manually ingest tool results into storage using `storage add` after a `rr` task completes.
4. **Tool Installation**: Prefer prebuilt binaries > `pipx` > `npx` for new tools.
5. **Preview Before View**: Check columns and entry count with `preview` to avoid fetching massive datasets.
6. **Server-side Filter**: Use `--filter` with the mandatory bitwise syntax for efficient querying.
7. **Annotate Often**: Document confirms vulnerabilities or findings via the annotation system.
8. **Chain with jq**: All `view` output is JSON, optimized for `jq` processing and automation.
9. **Check Context**: Use `rcn-app` or `rcn-marked` (when available) to maintain situational awareness.
