import asyncio
import sys
import os
from unittest.mock import MagicMock

# Mock dependencies
sys.modules["ruamel"] = MagicMock()
sys.modules["ruamel.yaml"] = MagicMock()
sys.modules["pentest_utils"] = MagicMock()
sys.modules["pentest_utils.storage"] = MagicMock()
sys.modules["pentest_utils.storage.shared"] = MagicMock()
sys.modules["pentest_utils.utils"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()
sys.modules["multidict"] = MagicMock()
sys.modules["xxhash"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["fnmatch"] = MagicMock()
sys.modules["watchdog"] = MagicMock()
sys.modules["watchdog.observers"] = MagicMock()
sys.modules["watchdog.events"] = MagicMock()
sys.modules["aiofiles"] = MagicMock()
sys.modules["rich"] = MagicMock()
sys.modules["rich.logging"] = MagicMock()
sys.modules["rich.console"] = MagicMock()
sys.modules["uvicorn"] = MagicMock()


class BaseSqliteStorage:
    pass


mock_shared = MagicMock()
mock_shared.BaseSqliteStorage = BaseSqliteStorage
sys.modules["pentest_utils.storage.shared"] = mock_shared

sys.path.append("/home/ahmed/programming-projects/python/rcn-core")

from rcn_core.data_access import (
    evaluate_combo_priority,
    get_entry_priority,
    get_multi_unprocessed_entries,
)


# Mocking Storage and Parent
class MockParent:
    def __init__(self, name="parent1"):
        self.name = name
        self.some_attr = "parent_attr"


class MockStorage:
    def __init__(self, name="storage1", parent=None, entries=None):
        self.storage_name = name
        self.parent_container = parent
        self.parent_id = 1
        self.entries = entries or []
        self.metadata = {}

    def get_all_entries(self):
        return self.entries

    def storage_md_get(self, key):
        return self.metadata.get(key)

    def storage_md_set(self, key, value):
        self.metadata[key] = value

    def reset_requester_metadata(self, name):
        pass


# Mock match_storage
def mock_match_storage(path, target=None):
    if path == "storage1":
        return [{"storage": s1, "parent": p1}]
    elif path == "storage2":
        return [{"storage": s2, "parent": p1}]
    return []


# Setup Data
p1 = MockParent("TestParent")
s1 = MockStorage(
    "storage1",
    p1,
    [
        {"id": "1", "url": "http://abc.com", "timestamp": 100},
        {"id": "2", "url": "http://xyz.com", "timestamp": 110},
    ],
)
s2 = MockStorage(
    "storage2",
    p1,
    [
        {"id": "A", "original_url": "http://abc.com", "timestamp": 105},
        {"id": "B", "original_url": "http://other.com", "timestamp": 115},
    ],
)


async def test_priority_evals_single_storage():
    print("--- Testing Single Storage Priority Evals ---")
    entry = {"id": "1", "val": 10, "status": "active"}

    # Test legacy behavior (entry variable)
    evals = ['entry["val"] > 5']
    p = get_entry_priority(evals, p1, s1, entry)
    print(f"Legacy get_entry_priority (entry['val'] > 5): {p} (Expected 1)")

    # Test new evaluate_combo_priority with single entry (backward compat)
    combo_list = [{"entry": entry, "storage": s1, "parent": p1}]
    evals = ['entry["val"] > 5']
    p = evaluate_combo_priority(evals, combo_list)
    print(f"New evaluate_combo_priority single (entry['val'] > 5): {p} (Expected 1)")

    # Test e1 variable
    evals = ['e1["val"] > 5']
    p = evaluate_combo_priority(evals, combo_list)
    print(f"New evaluate_combo_priority single (e1['val'] > 5): {p} (Expected 1)")


async def test_priority_evals_multi_storage():
    print("\n--- Testing Multi Storage Priority Evals (e1, e2) ---")

    # Create a combo: (s1_entry1, s2_entry_A) - should match (abc.com == abc.com)
    # Create a combo: (s1_entry1, s2_entry_B) - should NOT match (abc.com != other.com)

    combo1 = [
        {"entry": {"id": "1", "url": "http://abc.com"}, "storage": s1, "parent": p1},
        {
            "entry": {"id": "A", "original_url": "http://abc.com"},
            "storage": s2,
            "parent": p1,
        },
    ]

    combo2 = [
        {"entry": {"id": "1", "url": "http://abc.com"}, "storage": s1, "parent": p1},
        {
            "entry": {"id": "B", "original_url": "http://other.com"},
            "storage": s2,
            "parent": p1,
        },
    ]

    # Filter: Only keep combos where e1 url matches e2 original_url
    evals = ['1 if e1["url"] == e2["original_url"] else -1']

    res1 = evaluate_combo_priority(evals, combo1)
    print(f"Combo 1 (abc.com == abc.com): {res1} (Expected 1)")

    res2 = evaluate_combo_priority(evals, combo2)
    print(f"Combo 2 (abc.com != other.com): {res2} (Expected -1, filtered out)")

    # Test scoring: Add points for specific matches
    evals = [
        '1 if e1["url"] == e2["original_url"] else -1',
        '10 if e1["id"] == "1" else 0',
    ]

    res1 = evaluate_combo_priority(evals, combo1)
    print(f"Combo 1 with scoring: {res1} (Expected 11)")


async def test_multistorage():
    print("\n--- Testing MultiStorage Event Loop ---")

    event = {
        "require-storage": ["storage1", "storage2"],
        "max-entries": 10,
        "min-entries": 0,
        "priority-evals": ['1 if e1["url"] == e2["original_url"] else -1'],
    }

    print("Run 1: Initial check with priority filter")
    async with get_multi_unprocessed_entries(
        "scanner1", event, target=None, match_storage_fn=mock_match_storage
    ) as batch:
        print(f"Batch size: {len(batch)}")
        for key, item in batch.items():
            combo = item["entry"]
            ids = [e["entry"]["id"] for e in combo]
            priority = item.get("priority", "N/A")
            print(f"  Combo: {ids}, Priority: {priority}")

    state_key = "multi-unscanned:scanner1:state"
    state = s1.storage_md_get(state_key)
    print("State after Run 1:", state)


async def main():
    await test_priority_evals_single_storage()
    await test_priority_evals_multi_storage()
    await test_multistorage()


if __name__ == "__main__":
    asyncio.run(main())
