import sys
import os
import pathlib

sys.path.append("/home/ahmed/programming-projects/python/rcn-core")
sys.path.append("/home/ahmed/programming-projects/python/pentest-utils")

from rcn_core.storage.target_storage import MultiTargetStorage
from rcn_core.storage.implementations import get_storage
import rcn_core.globals

TARGET_DIR = "/home/ahmed/recon/new-target/"
storage_obj = MultiTargetStorage(TARGET_DIR)
rcn_core.globals.TARGET_STORAGE = storage_obj

print(f"Target ID: {storage_obj.targets_storage.get()[0]['id'] if storage_obj.targets_storage.get() else 'None'}")
print(f"Schema Cache keys before get_storage: {list(storage_obj.schema_cache.keys())}")

# Try to get web-apps using get_storage
st_list = get_storage("web-apps", parent_id=1755307742)
print(f"After get_storage('web-apps'), cache: {list(storage_obj.schema_cache.keys())}")
if st_list:
    st = st_list[0]
    print(f"st.initialized: {st.initialized}")
    print(f"st.has_data: {st.has_data}")
