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

The main CLI tool is `rcn-web-interact`. Use this for ALL server interactions.

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

**Update existing entries:**
```bash
rcn-web-interact <target_name> storage update --name <storage_name> --filter "<filter>" --updates '<json_data>' [--app-id <id>]
```
- Example: `rcn-web-interact my_target storage update --name "web-apps" --filter "(entry['site'] == 'old.site')" --updates '{"site": "new.site"}'`

**Delete entries from storage:**
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
- `potential-vuln`: `sqli`, `xss`, `idor`, `ssrf`
- `finding`: `api-key`, `secret`, `endpoint`
- `notes`: `interesting`, `suspicious`, `check-later`
- `todo`: `scan`, `analyze`, `verify`
- `acp-agent-do`: Delegation instructions

Example:
```bash
rcn-web-interact <target_name> annotate --storage "web-apps" --entry-id 123 --category "finding" --key "api-key" --value "Found AWS key in main.js"
```

#### Running Security Tools with rr

Basic syntax: `rr <program> <args>`
- **Nuclei**: `rr nuclei -u https://example.com/ -t http/exposed-panels/:l1`
- **FFUF**: `rr ffuf -u https://example.com/FUZZ:FUZZ -w ~/wordlists/common.txt:l1`

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

## Advanced Patterns

**Pipe to JQ and convert to entries for context saving:**
```bash
rcn-web-interact <target_name> view --storage "web-apps" | jq -c '.[]' | jsonl-to-entries
```

**Find API endpoints and extract URLs:**
```bash
rcn-web-interact view --storage "web-apps::app-links" --filter "entry['path'].contains('/api/')" | jq -r '.[].url'
```

## Best Practices

1. **Describe First**: Use `describe-target` to find dynamic storages.
2. **Preview Before View**: Check schema and count with `preview`.
3. **Server-side Filter**: Use `--filter` instead of `jq` for large datasets.
4. **Annotate Often**: Use the annotation system to persist findings.
5. **Chain with jq**: All `view` output is JSON, perfect for `jq` processing.
