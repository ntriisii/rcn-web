import sys
import os
import pathlib
import sqlite3

sys.path.append("/home/ahmed/programming-projects/python/rcn-core")
sys.path.append("/home/ahmed/programming-projects/python/pentest-utils")

from rcn_core.storage.bases import get_db_connection
from rcn_core.storage.implementations import BasicDataStorage
from pentest_utils.viewers.emacs.match_groups import parse_rule_to_node
from rcn_core.mcp.utils import render_storage_view
import rcn_core.globals

# Mock global storage
class MockMTS:
    def __init__(self):
        self.target_directory = pathlib.Path("/home/ahmed/recon/new-target/")
        self.schema_cache = {"web-apps": {}} # Mock schema cache
        self.id = 0
mock_mts = MockMTS()
rcn_core.globals.TARGET_STORAGE = mock_mts

st = BasicDataStorage(storage_name="web-apps", parent=mock_mts, parent_id=1755307742)

filter_str = "entry['id'].in_([924277511, 669653510, 593181651])"
node = parse_rule_to_node(filter_str)

print("--- Testing render_storage_view ---")
res = render_storage_view(st, filter=filter_str)
print(f"Result snippet: {res[:200]}")
