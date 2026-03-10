import os
import hashlib
import subprocess
import json
import shutil
import tempfile
import asyncio
import aiofiles as aiof
import re
from urllib.parse import urlparse
from rcn_core.log import rlog


async def get_js_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def run_command(cmd: list, cwd=None, input_data=None):
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if input_data else None,
            cwd=cwd,
        )
        stdout, stderr = await process.communicate(
            input=input_data.encode() if input_data else None
        )
        return process.returncode, stdout.decode(), stderr.decode()
    except Exception as e:
        return -1, "", str(e)


async def deobfuscate_js(js_content: str, url: str):
    """
    Uses webcrack to deobfuscate/deminify JS content.
    Returns a directory path containing the unpacked source.
    """
    tmp_dir = tempfile.mkdtemp(prefix="rcn_js_unpacked_")
    js_file = os.path.join(tmp_dir, "input.js")
    async with aiof.open(js_file, "w") as f:
        await f.write(js_content)

    # Use installed webcrack if available, otherwise fallback to npx
    webcrack_path = os.path.expanduser("~/.npm-global/bin/webcrack")
    unpacked_dir = os.path.join(tmp_dir, "unpacked")

    if os.path.exists(webcrack_path):
        cmd = [webcrack_path, js_file, "-o", unpacked_dir]
    else:
        # Fallback to npx -y
        npx_path = "/home/ahmed/.nix-profile/bin/npx"
        cmd = [npx_path, "-y", "webcrack", js_file, "-o", unpacked_dir]

    rc, stdout, stderr = await run_command(cmd)

    if rc != 0:
        rlog(f"webcrack failed for {url}: {stderr}", level="error")
        # If it fails, we just have the input file
        return tmp_dir, False

    return unpacked_dir, True


async def run_semgrep(target_path: str):
    """
    Runs semgrep on the target path with javascript security rules.
    """
    # Use installed semgrep
    semgrep_path = os.path.expanduser("~/.local/bin/semgrep")
    if not os.path.exists(semgrep_path):
        # Fallback to uvx
        semgrep_path = "/home/ahmed/.local/bin/uvx"
        cmd = [
            semgrep_path,
            "semgrep",
            "--config",
            "p/javascript",
            "--config",
            "p/owasp-top-10",
            "--json",
            target_path,
        ]
    else:
        cmd = [
            semgrep_path,
            "--config",
            "p/javascript",
            "--config",
            "p/owasp-top-10",
            "--json",
            target_path,
        ]

    rc, stdout, stderr = await run_command(cmd)
    if rc == 0:
        try:
            return json.loads(stdout).get("results", [])
        except:
            return []
    return []


def extract_secrets_regex(content: str):
    """
    Fallback regex-based secret extraction.
    """
    patterns = {
        "AWS API Key": r"AKIA[0-9A-Z]{16}",
        "Generic Secret": r"(?i)(key|secret|token|auth|password|passwd|pass)[\s:='\"]+[0-9a-zA-Z]{32,}",
        "Firebase URL": r"https://[a-z0-9.-]+\.firebaseio\.com",
        "Google API Key": r"AIza[0-9A-Za-z\\-_]{35}",
        "Slack Token": r"xox[baprs]-[0-9a-zA-Z]{10,48}",
    }
    findings = []
    for name, pattern in patterns.items():
        for match in re.finditer(pattern, content):
            findings.append(
                {
                    "kind": "regex-secret",
                    "reason": name,
                    "match": match.group(0),
                    "context": content[
                        max(0, match.start() - 50) : min(len(content), match.end() + 50)
                    ],
                }
            )
    return findings


async def run_jsluice(js_file_path: str):
    """
    Runs jsluice to extract urls and secrets.
    """
    findings = []
    # Use full path to jsluice
    jsluice_path = os.path.expanduser("~/go/bin/jsluice")
    if not os.path.exists(jsluice_path):
        jsluice_path = "/home/ahmed/.local/bin/jsluice"

    if not os.path.exists(jsluice_path):
        # Fallback to regex
        async with aiof.open(js_file_path, "r") as f:
            content = await f.read()
        return extract_secrets_regex(content)

    # URLs
    rc, stdout, stderr = await run_command([jsluice_path, "urls", js_file_path])
    if rc == 0:
        for line in stdout.splitlines():
            try:
                findings.append(json.loads(line))
            except:
                pass

    # Secrets
    rc, stdout, stderr = await run_command([jsluice_path, "secrets", js_file_path])
    if rc == 0:
        for line in stdout.splitlines():
            try:
                findings.append(json.loads(line))
            except:
                pass

    return findings


async def run_ppmap(url: str):
    """
    Runs ppmap on a URL to check for prototype pollution.
    """
    # ppmap expects input via stdin
    ppmap_path = os.path.expanduser("~/go/bin/ppmap")
    if not os.path.exists(ppmap_path):
        return ""
    rc, stdout, stderr = await run_command([ppmap_path], input_data=url)
    if rc == 0:
        return stdout.strip()
    return ""


def is_third_party(url: str, js_content: str) -> bool:
    """
    Heuristic to determine if JS is a standard third-party library.
    """
    common_libs = [
        "jquery",
        "react",
        "vue",
        "bootstrap",
        "moment",
        "lodash",
        "webpack",
        "vendor",
    ]
    url_lower = url.lower()
    if any(lib in url_lower for lib in common_libs) and (
        ".min.js" in url_lower or "node_modules" in url_lower
    ):
        return True

    # Check headers in content
    if js_content.startswith("/*!") or js_content.startswith("/**"):
        first_lines = js_content[:500].lower()
        if any(lib in first_lines for lib in common_libs):
            return True

    return False


_CURRENT_JXSCOUT_PROJECT = None
_CURRENT_JXSCOUT_SCOPE = None


async def start_jxscout(project_name: str, scope: str = None, port: int = 3333):
    """
    Starts jxscout as a background process.
    """
    global _CURRENT_JXSCOUT_PROJECT, _CURRENT_JXSCOUT_SCOPE
    jxscout_path = "/home/ahmed/.local/bin/jxscout"
    if not os.path.exists(jxscout_path):
        rlog(f"jxscout binary not found at {jxscout_path}", level="error")
        return False

    # Check if already running on that port
    import socket

    is_running = False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("localhost", port)) == 0:
            is_running = True

    # If running with different project or scope, we might need to restart it
    # For now, we just log it. In a real scenario we might want to kill the old process.
    if is_running:
        if _CURRENT_JXSCOUT_PROJECT == project_name and _CURRENT_JXSCOUT_SCOPE == scope:
            return True
        rlog(
            f"jxscout already running on port {port} (Project: {_CURRENT_JXSCOUT_PROJECT}, Scope: {_CURRENT_JXSCOUT_SCOPE}). Requested (Project: {project_name}, Scope: {scope})",
            level="warn",
        )
        # If project or scope changed, we should probably restart, but let's see if it works without it first
        # to avoid race conditions between different apps.
        return True

    cmd = [jxscout_path, "-port", str(port), "-project-name", project_name, "-debug"]
    if scope:
        cmd.extend(["-scope", scope])

    log_path = os.path.expanduser(f"~/jxscout/{project_name}/jxscout.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    env = os.environ.copy()
    env["TERM"] = "dumb"  # Try to disable TUI

    try:
        # Use a log file instead of DEVNULL for debugging
        log_file = open(log_path, "a")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=log_file,
            stderr=log_file,
            stdin=asyncio.subprocess.DEVNULL,
            env=env,
        )
        rlog(
            f"Started jxscout for project {project_name} on port {port}. Logs: {log_path}"
        )
        _CURRENT_JXSCOUT_PROJECT = project_name
        _CURRENT_JXSCOUT_SCOPE = scope
        # Wait for it to spin up

        await asyncio.sleep(2)
        return True
    except Exception as e:
        rlog(f"Failed to start jxscout: {e}", level="error")
        return False


async def run_nuclei_js(url: str):
    """
    Runs nuclei on a JS URL with specific security templates.
    """
    nuclei_path = "/home/ahmed/.local/bin/nuclei"
    if not os.path.exists(nuclei_path):
        return []

    rc, stdout, stderr = await run_command(
        [
            nuclei_path,
            "-it",
            "xss,prototype-pollution,postmessage,exposure,token,secret",
            "-u",
            url,
            "-jsonl",
        ]
    )
    findings = []
    if rc == 0:
        for line in stdout.splitlines():
            try:
                findings.append(json.loads(line))
            except:
                pass
    return findings


def get_jxscout_path(project_name: str):
    """
    Returns the path to jxscout's project directory.
    """
    return os.path.expanduser(f"~/jxscout/{project_name}")
