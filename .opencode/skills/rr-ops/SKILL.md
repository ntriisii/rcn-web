---
name: rr-ops
description: Comprehensive workflow for executing tools remotely using the rr (Remote Run) command.
---

# RR (Remote Run) Operations

This skill provides the operational protocol for executing reconnaissance and security tools on the remote RCN infrastructure.

## 1. Core Mandate: Remote First
All "running" commands (tools that perform network activity, scanning, fuzzing, or heavy computation) **MUST** be executed through the `rr` command. Do not execute these tools directly on the local machine.

## 2. The `rr` Command Syntax
Basic syntax:
```bash
rr <program> <args>
```

### Chunking Notation
Use `:l[n]` or `:p[n]` to distribute data across remote workers:
- `:l1`, `:l2`, ...: Distributes lines from a list/wordlist.
- `:p1`, `:p2`, ...: Distributes ports.

**Example (Nuclei):**
```bash
rr nuclei -l targets.txt:l1 -t cves/:l1
```

**Example (FFUF):**
```bash
rr ffuf -u http://HOST/FUZZ -w wordlist.txt:l1
```

### Remote Task Parameters
Use `---<param> <value>` (triple-dash) to pass configuration parameters to the remote task handler.

| Parameter | Description |
|-----------|-------------|
| `---task-name` | Name assigned to the remote task |
| `---local-only` | Only run the task on localhost |
| `---remote-only` | Don't run the task on localhost (remote nodes only) |
| `---no-distribute` | Run the task on only one host node (disables chunking) |
| `---chunks-count` | Explicitly set the number of chunks to create |
| `---chunk-length` | Number of items per chunk |
| `---min-chunk-length` | Minimum items per chunk (prevents creating tiny chunks) |
| `---chunks-per-host` | Number of concurrent chunks per host (default: 2) |
| `---serve-chunks-count` | Limit the total number of chunks to serve |
| `---begin` | Start index for processing the input list |
| `---timeout` | Task timeout in seconds |
| `---debug` | Enable debug mode for the task |
| `---host` | Target a specific host for execution |

**Example with parameters:**
```bash
rr nuclei -l targets.txt:l1 -t cves/ ---chunk-length 100 ---remote-only
```

## 3. Tool Installation Preferences
When a tool is not available on the remote nodes, follow this order of preference for installation:
1. **Prebuilt Binaries**: The primary and most efficient choice.
2. **Pipx (Python)**: Use `pipx install <package_name>`.
3. **Npx (Node.js)**: Use `npx <package_name>`.

## 4. Manual Scanning Workflow
The system relies on a manual execution and ingestion cycle:

1. **Execute**: Run the tool using `rr`.
2. **Completion**: Wait for the remote task to finish and retrieve results.
3. **Ingest**: Manually add the discovered data to the `rcn-web` storage using:
   ```bash
   rcn-web-interact <target> storage add --name <storage_name> --data '<json_results>'
   ```
4. **Annotate**: If the data represents a specific finding, use:
   ```bash
   rcn-web-interact <target> annotate ...
   ```

## 5. Workflow Example
```bash
# 1. Run nuclei remotely
rr nuclei -u https://example.com -t cves/ -jsonl > results.jsonl

# 2. Ingest results into storage (example of manual piping/formatting)
cat results.jsonl | jq -c '.' | while read line; do
  rcn-web-interact my-target storage add --name "web-apps::nuclei-scanning" --data "$line"
done
```
