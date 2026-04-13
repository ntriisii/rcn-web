---
name: rcn-web
description: Use when the user needs to browse discovered recon assets, explore hierarchical reconnaissance data, or orchestrate automated security scans on the RCN Web platform.
---

# RCN Web Reconnaissance Platform

This skill provides complete control over the RCN Web reconnaissance and scanning platform for systematic target management, data exploration, and automated security testing.

## Server Information

The RCN Web platform provides a command-line interface for all interactions. Use only the provided tools and commands—do not attempt to connect directly to any server URLs.

## Storage Hierarchy

Storages use `::` as a hierarchical separator. Always use `rcn-web-interact <target_name> describe-target` once you start any work to discover available storages and their schemas dynamically.


## Primary Interface: rcn-web-interact

The main CLI tool is `rcn-web-interact`. Use this for ALL server interactions.

### Arguments

- `TARGET`: Target name. This is a mandatory positional argument used to route requests to the target-specific service.

### Global Options

All commands support the following global options:

### Command Reference

#### Describe Target (Initial Setup)

**Describe the target and list all available storages:**
```bash
rcn-web-interact <target_name> describe-target
```

This command should be run FIRST when starting work. It returns (don't rerun if it has been ran before and you understand the target):
- Target metadata (name, scope, etc.)
- List of all available storages with entry counts
- Sample of columns available in each storage

the target_name is the current directory name you're in ie ~/recon/<target_name>

#### Storage Preview (Metadata)

**Preview storage before viewing (use to check available columns):**
```bash
rcn-web-interact <target_name> preview --storage <storage_name> [--filter "<filter>"] [--page <n>] [--limit <m>]
```

Examples:
```bash
# Preview web-apps storage (list all applications)
rcn-web-interact my_target preview --storage "web-apps"

# Preview with filter (use entry['<column_name>'] syntax)
rcn-web-interact <target_name> preview --storage "web-apps" --filter "entry['status_code'] == 200"

# Preview with pagination
rcn-web-interact <target_name> preview --storage "web-apps" --page 1 --limit 50

# Preview app-specific storage
rcn-web-interact <target_name> preview --storage "web-apps::js-flows" --filter "entry['site'] == 'example.com'"
```

**Preview shows:**
- Item count
- Available columns/schema

#### Storage View (Actual Data)

**View entries in any storage:**
```bash
rcn-web-interact <target_name> view --storage <storage_name> [--filter "<filter>"] [--page <n>] [--limit <m>]
```

All storages support `--filter`, `--page`, and `--limit` parameters uniformly. The columns returned in the view correspond to the fields inside the `entry` dictionary.

Examples:
```bash
# View applications (generic approach - works on all storages)
rcn-web-interact <target_name> view --storage "web-apps"
rcn-web-interact <target_name> view --storage "web-apps" --filter "entry['status_code'] == 200" --limit 100

# Filter for specific patterns
rcn-web-interact <target_name> view --storage "web-apps::js-flows" --filter "entry['url'].contains('api/v1')"

# Filter for 403 pages
rcn-web-interact <target_name> view --storage "web-apps::app-links" --filter "entry['status'] == 403"
```

#### Annotations System

The annotation system is a centralized meta-layer for tagging entries, tracking findings, and managing tasks. Every annotation has THREE MANDATORY components:

1. **Category** (mandatory) - The high-level grouping
2. **Key** (mandatory) - Specific identifier within the category
3. **Value** (mandatory) - The actual content/data

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
| `acp-agent-do` | Delegate to ACP agent | `<agent-name>` | XML with instructions |
| `notify` | User notifications | `alert`, `info` | Notification message |

**Examples:**
```bash
# Mark potential vulnerability (category is MANDATORY)
rcn-web-interact <target_name> annotate --storage "web-apps::app-links" --entry-id 456 --category "potential-vuln" --key "sqli" --value "Possible SQL injection in search parameter"

# Add finding
rcn-web-interact <target_name> annotate --storage "web-apps::js-flows" --entry-id 789 --category "finding" --key "api-key" --value "Found hardcoded AWS key in main.js: AKIA..."

# Add TODO
rcn-web-interact <target_name> annotate --storage "web-apps" --entry-id 123 --category "todo" --key "scan" --value "Run nuclei scan on admin endpoints"

# Delegate to ACP agent (special format)
rcn-web-interact <target_name> annotate --storage "web-apps::js-flows" --entry-id 101 --category "acp-agent-do" --key "gemini-3-flash" --value "<instruction>Analyze JS for API endpoints</instruction>"
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

nuclei-templates are in /home/ahmed/AllForOne/Templates/

**Running FFUF:**
```bash
# Fuzz with wordlist distribution
rr ffuf -u https://example.com/FUZZ:FUZZ -w ~/wordlists/common.txt:l1

# Fuzz multiple targets
rr ffuf -u l1:FUZZ -w ~/wordlists/api-endpoints.txt:l2
```

**Saving Results to Storages:**

After running tools, add findings to the appropriate storage. Data should be added as valid JSON matching the schema of the storage:

```bash
# Add nuclei results to scanning storage
rcn-web-interact add --storage "web-apps::nuclei-scanning" --app "example.com" --data '{"name": "CVE-2021-1234", "severity": "high", "url": "https://example.com/admin"}'

# Add fuzzing results
rcn-web-interact add --storage "web-apps::fuzzing-data" --app "example.com" --data '{"url": "https://example.com/api/v1/users", "status": 200, "length": 1500}'
```

## Filter Syntax

The filtering system uses a custom python objects that will be translated to sql filters, only use the provided rules when creating filters:

**CRITICAL RULES:**
1. You MUST use bitwise operators `&` (AND) and `|` (OR) for logical combinations. Do NOT use Python's `and` / `or`.
2. You MUST wrap individual comparisons in parentheses `()` when using bitwise operators.
3. Do NOT use `re.search`, `in`, or standard Python string methods. Use the provided `.contains()` and `.in_()` methods.

### Basic Filter Examples

```bash
# Equality
--filter "entry['status_code'] == 200"
--filter "entry['site'] == 'example.com'"

# Comparison
--filter "entry['content_length'] > 1000"
--filter "entry['content_length'] <= 10000"

# Substring matching (translates to LIKE %...%)
--filter "entry['url'].contains('api')"
--filter "entry['technologies'].contains('React')"

# Multiple conditions with bitwise operators (Parentheses are REQUIRED)
--filter "(entry['status'] == 200) & (entry['url'].contains('api'))"
--filter "(entry['site'] == 'example.com') | (entry['site'] == 'api.example.com')"
--filter "(entry['status'].in_([200, 201])) & (entry['method'] == 'POST')"

# Negation (translates to != or NOT LIKE)
--filter "entry['status'] != 404"

# Membership checks
--filter "entry['status'].in_([200, 201, 204])"
--filter "entry['site'].in_(['example.com', 'test.com'])"

```

### Filter Patterns for Common Use Cases

**Find apps by technology:**
```bash
--filter "entry['technologies'].contains('PHP')"
--filter "entry['technologies'].contains('Next.js')"
```

**Find API endpoints:**
```bash
--filter "(entry['url'].contains('api')) & (entry['status'] == 200)"
--filter "entry['path'].contains('/api/v')"
```

**Find specific file types:**
```bash
--filter "(entry['path'].contains('.php')) | (entry['path'].contains('.asp'))"
--filter "entry['url'].contains('.js')"
```

## Advanced Command Patterns

The output of `rcn-web-interact view` is a JSON list. Use `jq` for filtering/extraction or `jsonl-to-entries` for human-readable compact views.

### jsonl-to-entries (Recommended for context saving)

Use `jsonl-to-entries` to convert JSONL data into compact ##-separated entry blocks. This saves context tokens compared to raw JSON output. Pipe the JSON list output from `view` through `jq` to convert to JSONL first:

```bash
rcn-web-interact <target_name> view --storage "web-apps" | jq -c '.[]' | jsonl-to-entries
```

**Examples:**
```bash
# View all applications in compact format
rcn-web-interact <target_name> view --storage "web-apps" | jq -c '.[]' | jsonl-to-entries

# View filtered results
rcn-web-interact <target_name> view --storage "web-apps" --filter "entry['status_code'] == 200" | jq -c '.[]' | jsonl-to-entries

# View specific fields only (saves even more tokens)
rcn-web-interact <target_name> view --storage "web-apps" | jq -c '.[] | {site, url, status_code}' | jsonl-to-entries
```

**Example output:**
```
keys:
site
url
status_code
-------
and it will be seperated by ##

example.com
https://example.com
200
##
test.com
https://test.com/api
403
##
```

### Parse and Filter Output with JQ

**Get applications and extract URLs:**
```bash
rcn-web-interact view --storage "web-apps" | jq -r '.[].url'
```

**Get apps with specific technology:**
```bash
rcn-web-interact view --storage "web-apps" --filter "entry['technologies'].contains('React')" | jq '.[] | {site, url, technologies}'
```

**Extract links and format for testing:**
```bash
rcn-web-interact view --storage "web-apps::app-links" --filter "entry['site'] == 'example.com'" | jq -r '.[] | "\(.status) \(.url)"' | sort -n
```

**Get JS files from marked apps:**
```bash
rcn-apps | jq -r '.[] | .site' | while read app; do
  rcn-web-interact view --storage "web-apps::js-flows" --filter "entry['site'] == '$app'" | jq -r '.[] | .url'
done
```

## Scripting and Automation

### Python Integration

you can always use the skill rcn-scheduled-events to create those.

When working with scheduled functions (use `@rcn_event` decorator):

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

1. **Start with describe-target** - Always run `describe-target` first to see available storages
2. **Use preview to check columns** - Preview storage before querying to understand available columns
3. **Filter server-side** - Use `--filter` with the entry['column'] syntax instead of filtering client-side with jq
4. **Paginate large results** - Use `--page` and `--limit` for large storages
5. **Annotate findings** - Use `annotate` with mandatory category/key/value to document discoveries
6. **Delegate heavy tasks** - Use `delegate` for time-consuming analysis
7. **Chain with jq** - Pipe outputs to `jq` for transformation after server-side filtering
8. **Check context first** - Always check `rcn-app` or `rcn-marked` for current context
