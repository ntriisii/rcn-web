import asyncio
import os
import sys
import yaml

sys.path.insert(0, "/home/ahmed/programming-projects/python/rcn-core")
sys.path.insert(0, "/home/ahmed/programming-projects/python/rcn-web")

target_dir = os.path.expanduser("~/recon/github/")
os.chdir(target_dir)

from rcn_web.core.utils import web_match_storage
from rcn_core.data_access import get_unprocessed_annotations, get_storage
import rcn_core.globals
from rcn_core.storage.target_storage import TargetStorage

# Load the YAML config
with open(os.path.join(target_dir, "targets.yaml"), "r") as f:
    config = yaml.safe_load(f)
rcn_core.globals.YAML_FILE_CONTENT = config
rcn_core.globals.TARGET_DIR = target_dir


async def run_test():
    print("Initializing storage...")
    storage = TargetStorage("github", ".")
    rcn_core.globals.TARGET_STORAGE = storage

    print("Testing web_match_storage...")
    matched = web_match_storage("web-apps::annotations", target=storage)
    print("Matched length:", len(matched))
    if matched:
        print("Matched[0] keys:", list(matched[0].keys()))

    print("Testing scanning event...")
    event_data = {
        "name": "check-scanning-aiannotated-tool2",
        "require-storage": "web-apps::annotations",
        "priority-evals": ["1 if entry.get('category') == 'tool-scanning' else -1"],
    }

    async with get_unprocessed_annotations(
        "tool-scanning",
        "check-scanning-aiannotated-tool2",
        event_data,
        match_storage_fn=web_match_storage,
    ) as unscanned:
        print("Unscanned length:", len(unscanned))

        # Test directly querying the storage
        st = matched[0]["storage"]
        print("Storage has_data:", st.has_data)
        print("Storage table:", st._safe_table_name)
        print("Storage scope:", getattr(st, "_scope_name", None))
        items = st.get_filtered("1=1")
        print("Direct storage items length:", len(items))
        if items:
            print("First item category:", items[-1].get("category"))


if __name__ == "__main__":
    asyncio.run(run_test())
