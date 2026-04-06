---
name: rcn-target-ops
description: Investigate, start, restart, and debug running RCN targets.
---

# RCN Target Operations
Investigate, start, restart, and debug running RCN targets.

## STARTING TARGETS
To start a main web server for a target:
```bash
./.venv/bin/python -m rcn_web <target_dir> --port <port>
```
To start the mitmproxy reverse proxy:
```bash
mitmproxy -s server.py
```

## INVESTIGATING RUNNING TARGETS
Check for running processes and their ports:
```bash
ps aux | grep rcn_web
```
Verify port connectivity:
```bash
curl -I http://localhost:<port>/mcp/tools
```

## RESTARTING TARGETS
### Via Proxy API (Recommended)
The proxy server (usually port 8023) provides an endpoint to force-reload downstream instances:
```bash
curl -X POST http://localhost:8023/restartTarget/<target_name>
```

### Manual Restart
1. Find the PID: `ps aux | grep rcn_web`
2. Kill the process: `kill -9 <PID>`
3. The proxy will automatically respawn it on the next request, or you can start it manually using the command in "STARTING TARGETS".

## DEBUGGING RUNNING INSTANCES
### Logs
Check system-level logs if redirection is active, or use `/tmp/mcp_debug.log` for custom trace injections.

### Direct API Testing
Test storage resolution and filters without using the proxy:
```bash
curl -X POST http://localhost:<target_port>/mcp/view \
-H "Content-Type: application/json" \
-d '{"collection": "web-apps", "limit": 1}'
```

## COMMON PITFALLS
- **Port Conflicts**: Ensure no other process is using the target port (8031+).
- **Target Mismatch**: Verify the `<target_dir>` passed to `rcn_web` matches the database you are investigating.
- **Venv Missing**: Always use `./.venv/bin/python` to ensure dependencies like `xxhash` and `aiohttp` are available.
