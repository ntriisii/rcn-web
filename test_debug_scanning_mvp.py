import asyncio
import os
import sys
import json
import rcn_core.globals
from rcn_core.storage.target_storage import MultiTargetStorage
from rcn_web.scanning.mcp_scanners import mcp_ai_perform_scanning
from rcn_web.core.utils import web_match_storage, get_apps, get_uniq_apps
import rcn_core.parse_yaml as pyaml


async def main():
    target_dir = os.path.expanduser("~/recon/github/")
    rcn_core.globals.TARGET_DIR = target_dir
    storage_obj = MultiTargetStorage(target_dir)
    rcn_core.globals.TARGET_STORAGE = storage_obj

    target = list(storage_obj.targets.values())[0]
    rcn_core.globals.TARGET_CONFIG = target.config
    rcn_core.globals.YAML_FILE_CONTENT = target.config

    # Mock event data
    event = {
        "name": "check-scanning-aiannotated-tool",
        "enabled": True,
        "every": "30s",
        "require-storage": "web-apps::annotations",
    }

    print(f"Running mcp_ai_perform_scanning with event: {event}")
    await mcp_ai_perform_scanning(event, {})
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
