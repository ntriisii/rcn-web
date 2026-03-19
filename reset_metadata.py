import pickle
import os

target_path = os.path.expanduser("~/recon/github/github.pickle")
with open(target_path, "rb") as f:
    target = pickle.load(f)

scanner_name = "check-scanning-aiannotated-tool"
category = "tool-scanning"
actual_requester = f"{scanner_name}:{category}"
key = actual_requester + "-last-id-timestamp"

print(f"Old Metadata for {key}: {target.storage_md_get(key)}")
target.storage_md_set(key, 0)
print(f"New Metadata for {key}: {target.storage_md_get(key)}")

with open(target_path, "wb") as f:
    pickle.dump(target, f)

print("Metadata reset successfully.")
