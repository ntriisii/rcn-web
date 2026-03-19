import asyncio
import os
import sys
import json
import rcn_core.globals
from rcn_core.storage.target_storage import MultiTargetStorage
from rcn_web.core.utils import web_match_storage


async def main():
    target_dir = os.path.expanduser("~/recon/github/")
    rcn_core.globals.TARGET_DIR = target_dir
    storage_obj = MultiTargetStorage(target_dir)
    rcn_core.globals.TARGET_STORAGE = storage_obj

    target = list(storage_obj.targets.values())[0]
    print(f"Target ID: {target.id}")

    st = target.get_storage_create("web-apps")
    print(f"web-apps storage ID: {st.id}")
    print(f"web-apps storage parent_id: {st.parent_id}")

    ann_st = st.annotations_storage
    print(f"web-apps annotations storage parent_id: {ann_st.parent_id}")


if __name__ == "__main__":
    asyncio.run(main())
