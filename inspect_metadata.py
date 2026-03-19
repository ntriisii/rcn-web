import pickle
import os

target_path = os.path.expanduser("~/recon/github/github.pickle")
with open(target_path, "rb") as f:
    target = pickle.load(f)

print("Metadata keys matching 'check-scanning-aiannotated-tool':")
for k in target._storage_metadata:
    if "check-scanning-aiannotated-tool" in k:
        print(f"{k}: {target._storage_metadata[k]}")
