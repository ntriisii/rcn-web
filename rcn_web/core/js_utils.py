import os
import hashlib
import re
from rcn_core.log import rlog


async def get_js_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


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


# Legacy functions (referenced by legacy code in backup)
async def run_command(*args, **kwargs):
    pass


async def deobfuscate_js(*args, **kwargs):
    return None, False


async def run_semgrep(*args, **kwargs):
    return []


async def run_jsluice(*args, **kwargs):
    return []


async def run_ppmap(*args, **kwargs):
    return ""


async def start_jxscout(*args, **kwargs):
    return False


async def run_nuclei_js(*args, **kwargs):
    return []


def get_jxscout_path(*args, **kwargs):
    return ""
