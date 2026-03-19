import asyncio
import os
import sys
import json
import rcn_core.globals
from rcn_core.storage.target_storage import MultiTargetStorage
from rcn_web.core.scope import get_target_scope


async def main():
    target_dir = os.path.expanduser("~/recon/github/")
    rcn_core.globals.TARGET_DIR = target_dir
    storage_obj = MultiTargetStorage(target_dir)
    rcn_core.globals.TARGET_STORAGE = storage_obj

    target = list(storage_obj.targets.values())[0]
    print(f"Target config: {target.config}")
    scope = get_target_scope()
    print(f"Target scope: {scope}")


if __name__ == "__main__":
    asyncio.run(main())
