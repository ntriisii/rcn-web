---
name: rcn-web
description: Use when the user needs to browse discovered applications, explore hierarchical reconnaissance data, or orchestrate automated security scans (Nuclei/FFUF) on the RCN Web platform.
---

# RCN Web Reconnaissance Platform

This skill provides complete control over the RCN Web reconnaissance and scanning platform for systematic target management, data exploration, and automated security testing.

## Server Information

The RCN Web platform provides a command-line interface for all interactions. Use only the provided tools and commands—do not attempt to connect directly to any server URLs.

## Core Architecture

### System Organization
The system organizes data into **Targets**, **Web Applications**, and **Storages**:

- **Target**: A scope or project containing multiple applications
- **Web Application**: A specific site/host (e.g., `example.com:443`)
- **Storage**: A named collection of entries, hierarchical using the `::` separator

### Storage Hierarchy

Storages use `::` as a hierarchical separator. Always use `rcn-web-interact <target_name> describe-target` once you start any work to discover available storages and their schemas dynamically.


### Flow Data Structure
a flow is anything that has its ID as flow-id and is a timestamp, make sure to treat them using the ewp-interact tool, as those are related and stored at that project.
HTTP flows (network traffic) contain:
- `method` - HTTP method
- `url` - Full request URL
- `path` - URL path
- `request-headers` - MultiDict of request headers
- `request-body` - Request body
- `status` - Response status code
- `response-headers` - MultiDict of response headers
- `response-body` - Response body

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

#### Storage Preview (Metadata)

**Preview storage before viewing (use to check available columns):**
```bash
# Note: Use entry['<column_name>'] syntax for all filters
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
# Note: Use entry['<column_name>'] syntax for all filters
rcn-web-interact <target_name> view --storage <storage_name> [--filter "<filter>"] [--page <n>] [--limit <m>]
```

All storages support `--filter`, `--page`, and `--limit` parameters uniformly. The columns returned in the view correspond to the fields inside the `entry` dictionary.

Examples:
```bash
# View applications (generic approach - works on all storages)
rcn-web-interact <target_name> view --storage "web-apps"
rcn-web-interact <target_name> view --storage "web-apps" --filter "entry['status_code'] == 200" --limit 100
rcn-web-interact <target_name> view --storage "web-apps" --filter "entry['technologies'].contains('React')" --page 2 --limit 50

# View links for a specific app
rcn-web-interact <target_name> view --storage "web-apps::app-links" --filter "entry['site'] == 'example.com'"

# Filter for specific patterns
rcn-web-interact <target_name> view --storage "web-apps::js-flows" --filter "entry['url'].contains('api/v1')"


# Filter for 403 pages
rcn-web-interact <target_name> view --storage "web-apps::app-links" --filter "entry['status'] == 403"

# View nuclei scan results with pagination
rcn-web-interact <target_name> view --storage "web-apps::nuclei-scanning" --filter "entry['site'] == 'example.com'" --page 1 --limit 20

# View fuzzing results
rcn-web-interact <target_name> view --storage "web-apps::fuzzing-data" --filter "entry['status'] == 200" --limit 100
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

#### ACP Delegation

**Delegate tasks to background agents:**
```bash
rcn-web-interact <target_name> delegate --app <name> --agent <agent_name> --instructions "<text>" --storage <storage_name> [--entry-ids <ids>]
```

Available agents:
- `gemini-3-flash` - Fast analysis agent
- `gemini-3` - Standard analysis agent

Examples:
```bash
# Delegate JS analysis
rcn-web-interact <target_name> delegate --app "example.com" --agent "gemini-3-flash" --instructions "Analyze all js-flows for hardcoded credentials and internal staging URLs." --storage "web-apps::js-flows"

# Delegate specific entries
rcn-web-interact <target_name> delegate --app "example.com" --agent "gemini-3" --instructions "Check these endpoints for IDOR vulnerabilities" --storage "web-apps::app-links" --entry-ids "1,2,3"
```

#### Running Security Tools with rr

The `rr` command distributes scanning tasks across workers. It runs tools like nuclei, ffuf, and dalfox with chunked wordlists for parallel execution.

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
rr nuclei -u https://example.com/ -t http/exposed-panels/

# Scan multiple URLs from file
rr nuclei -l /path/to/urls.txt:l1 -t http/cves/
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

**Available Tool Programs:**
- `nuclei` - Vulnerability scanner
- `ffuf` - Fuzzing tool

#### Scheduled Functions

Create persistent background automations by creating scheduled functions. The scheduled function consists of two parts: a YAML configuration file and a Python script containing the logic. Both files should be created in the current target's root directory.

**Create a new scheduled function:**

1. Create the YAML configuration file in the project root:
   ```yaml
   # my-scanner.yaml
   name: my_scanner
   every: 10m
   require-storage: web-apps
   min-entries: 1
   function: py_my_scanner
   ```

2. Create the Python script in the same directory:
   ```python
   # script.py (or another python file in the root directory)
   from rcn_core.decorators import rcn_event
   from rcn_core.data_access import get_unprocessed_entries
   
   @rcn_event()
   async def my_scanner(event, scheduled_md):
       async with get_unprocessed_entries(event["name"], event) as unprocessed:
           if not unprocessed:
               return
           for item_id, item_data in unprocessed.items():
               entry = item_data['entry']
               # Process entry
               print(f"Processing: {entry.get('url')}")
   ```

**Schedule formats:**
- `10s` - 10 seconds
- `10m` - 10 minutes
- `1h` - 1 hour
- `1d` - 1 day
- `10s 10m 10h 10d` - Combined intervals

**Key parameters in YAML:**
- `name` - Function identifier
- `every` - Execution interval
- `require-storage` - Storage to monitor for new entries
- `min-entries` - Minimum new entries before triggering (optional)
- `function` - The name of the python function prefixed with `py_` (e.g., `py_my_scanner` refers to `def my_scanner`)

**Multi-storage patterns:**
```yaml
name: correlate_data
require-storage:
  - web-apps
  - web-apps::js-flows
```

This triggers when new entries exist in BOTH storages, providing combinations.

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

## Advanced Command Patterns with JQ

the output of the `rcn-web-interact view` command will always be json list so you can use 
jq to parse and filter required content to focus on information that is crucial and required.
### Parse and Filter Output

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



## Common Workflow Patterns

### Pattern 1: Initial Setup - Describe Target
```bash
# Always start by describing the target
rcn-web-interact describe-target

# This shows all available storages and their entry counts
```

### Pattern 2: Application Discovery
```bash
# Use view --storage "web-apps" for all app operations
rcn-web-interact view --storage "web-apps"

# Filter by technology
rcn-web-interact view --storage "web-apps" --filter "entry['technologies'].contains('PHP')" --limit 100

# Find unchecked apps
rcn-web-interact view --storage "web-apps" --filter "entry['app_checked'] == 0" --page 1 --limit 50

# Find apps by domain pattern
rcn-web-interact view --storage "web-apps" --filter "entry['site'].contains('api')" --limit 20
```

### Pattern 3: Storage Exploration
```bash
# Preview storage to see columns
rcn-web-interact preview --storage "web-apps::js-flows"

# View with appropriate filters
rcn-web-interact view --storage "web-apps::js-flows" --filter "entry['url'].contains('.min.js')" --limit 100
```

### Pattern 4: Targeted Data Retrieval
```bash
# Filter for interesting patterns
rcn-web-interact view --storage "web-apps::app-links" --filter "(entry['url'].contains('api/v1')) & (entry['status'] == 200)" --limit 50

# Find endpoints with specific extensions
rcn-web-interact view --storage "web-apps::app-links" --filter "((entry['path'].contains('.php')) | (entry['path'].contains('.asp'))) & (entry['status'] == 200)"
```

### Pattern 5: Security Analysis with Annotations
```bash
# Mark findings using annotate command
rcn-web-interact annotate --storage "web-apps::app-links" --entry-id 456 --category "finding" --key "admin-panel" --value "Found admin panel at /admin"

# Trigger nuclei scan on discovered endpoints
rcn-web-interact scan --app "example.com" --xml "<scanning><base-url>https://example.com/admin</base-url><templates>http/exposed-panels/admin-panel.yaml</templates></scanning>"
```

### Pattern 6: Bulk Operations
```bash
# Get all unchecked apps and process them
rcn-web-interact view --storage "web-apps" --filter "entry['app_checked'] == 0" --limit 100 | jq -r '.[].site' | while read site; do
echo "Processing $site..."
# Use rcn-web-interact commands to modify state
rcn-web-interact annotate --storage "web-apps" --entry-id "$site" --category "run" --key "checked" --value "true"
done
```

### Pattern 7: Delegation for Deep Analysis
```bash
# Delegate JS analysis to background agent
rcn-web-interact delegate --app "example.com" --agent "gemini-3-flash" --instructions "Analyze all JavaScript files for: 1) Hardcoded API keys/secrets, 2) Internal endpoints/URLs, 3) Source map references, 4) Sensitive configuration data" --storage "web-apps::js-flows"
```

## Scripting and Automation

### Shell Script Examples

**Process all applications:**
```bash
#!/bin/bash
rcn-web-interact view --storage "web-apps" --filter "entry['disabled'] == 0" --limit 1000 | jq -r '.[].site' | while read app; do
  echo "Processing $app..."
  # Your processing logic here
done
```

**Extract all URLs for fuzzing:**
```bash
#!/bin/bash
SITE="example.com"
rcn-web-interact view --storage "web-apps::app-links" --filter "(entry['site'] == '$SITE') & (entry['status'] == 200)" --limit 1000 | \
  jq -r '.[] | .url' > urls.txt
```

**Check for new JS files (using annotation tracking):**
```bash
#!/bin/bash
rcn-web-interact <target_name> view --storage "web-apps::js-flows" --filter "entry['site'] == 'example.com'" --limit 100 | \
  jq -r '.[] | .url' | while read url; do
    echo "JS File: $url"
done
```

### Python Integration

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

## Available Tools

- `rcn-web-interact`: Core CLI for all RCN Web operations
- `jq`: JSON processor for filtering output

## Annotation Categories Reference

**Entry Categories:**
- `potential-vuln` - Potential vulnerabilities
- `notes` - General observations
- `run` - Execution parameters

**User Categories:**
- `notify` - User notifications
- `finding` - Security findings

**ACP Agent Category:**
- `acp-agent-do` - Task delegation
  - Key: Agent name
  - Value: XML with `<instruction>`, `<repeat>`, `<entry>`

