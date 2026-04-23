---
name: rcn-web-interact
description: Use when the user needs to browse discovered recon assets, explore hierarchical reconnaissance data, or orchestrate automated security scans on the RCN Web platform.
---

# RCN Web Reconnaissance Platform

This skill provides complete control over the RCN Web reconnaissance and scanning platform for systematic target management, data exploration, and automated security testing.

## Server Information

The RCN Web platform provides a command-line interface for all interactions. Use only the provided tools and commands.

## Storage Operations (CRITICAL)

All storage operations (preview, view, add, update, delete, annotate) use the standard `rcn-storage-ops` structure.

**Base Command:** `rcn-web-interact`

Example:
```bash
rcn-web-interact storage view --name "web-apps"
```

See the **rcn-storage-ops** skill for detailed filter syntax and command options.

## Primary Interface: rcn-web-interact

### Describe Target (Initial Setup)

**Describe the target and list all available storages:**
```bash
rcn-web-interact describe-target
```

This command should be run FIRST when starting work. It returns:
- Target metadata (ID, Site)
- List of all available storages with entry counts
- Sample of columns available in each storage

### Annotations System

Every annotation requires: **Category**, **Key**, and **Value**.

**Add an annotation to an entry:**
```bash
rcn-web-interact annotate --storage <storage> --entry-id <id> --category <cat> --key <key> --value <val>
```

**Standard Categories:** `potential-vuln`, `finding`, `notes`, `todo`, `acp-agent-do`, `notify`.

### Running Security Tools with rr

The `rr` command distributes scanning tasks across workers.

**Basic rr syntax:**
```bash
rr <program> <args>
```

**Running Nuclei:**
```bash
rr nuclei -u https://example.com/ -t http/exposed-panels/:l1
```

**Running FFUF:**
```bash
rr ffuf -u https://example.com/FUZZ:FUZZ -w ~/wordlists/common.txt:l1
```

### MCP Actions and Prompts

- **List tools/prompts**: `rcn-web-interact list-tools` or `list-prompts`
- **Execute Action**: `rcn-web-interact action --name <name> [--params '<json>']`
- **Execute Prompt**: `rcn-web-interact prompt --name <name> [--args '<json>']`

## Best Practices

1. **Describe First**: Use `describe-target` to find dynamic storages and schemas.
2. **Remote Execution**: Always run scanning/fuzzing tools through `rr` (see `rr-ops` skill).
3. **Manual Ingestion**: Manually ingest tool results into storage using `storage add` after a `rr` task completes.
4. **Annotate Often**: Document confirms vulnerabilities or findings via the annotation system.
