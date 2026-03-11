
import asyncio
import time
import random
import string
import tempfile
from collections import defaultdict
from urllib.parse import urlparse

from rcn_core.data_access import match_storage
from rcn_core.data_access import get_unprocessed_entries, get_multi_unprocessed_entries
from rcn_web.core.utils import add_apps, get_apps, get_uniq_apps, web_match_storage
from rcn_core.data_access import get_storage


def generate_random_data(num_entries, types=None):
    """Generates a list of random data entries."""

    data = []
    for i in range(num_entries):
        if types:
            entry = {}
            for key, type_info in types.items():
                entry_type = type_info["type"]
                if entry_type in ["int", "integer"]:
                    entry[key] = random.randint(0, 100)
                elif entry_type in ["str", "string"]:
                    length = type_info.get("len", 20)
                    entry[key] = "".join(
                        random.choices(string.ascii_letters + string.digits, k=length)
                    )
                elif entry_type in ["url"]:
                    length = type_info.get("len", 20)
                    entry[key] = (
                        f"http://test.com/{''.join(random.choices(string.ascii_lowercase, k=length))}"
                    )
                elif entry_type in ["bool", "boolean"]:
                    entry[key] = random.choice([True, False])
                elif entry_type in ["float", "double"]:
                    entry[key] = random.uniform(0.0, 100.0)
                elif entry_type in ["path", "filename"]:
                    extensions = type_info.get("extensions", [".txt"])
                    prefix = type_info.get("prefix", "")
                    base_filename = type_info.get("filename")
                    increment = type_info.get("increment", False)

                    if base_filename:
                        filename = base_filename
                    else:
                        filename = "".join(random.choices(string.ascii_lowercase, k=random.randint(5, 15)))

                    if increment:
                        filename = f"{filename}{i + 1}"

                    ext = random.choice(extensions)
                    if not ext.startswith("."):
                        ext = "." + ext

                    if prefix:
                        if not prefix.endswith("/"):
                            prefix += "/"
                        entry[key] = f"{prefix}{filename}{ext}"
                    else:
                        entry[key] = f"/{filename}{ext}"
                else:
                    # Default to string with 20 chars if unknown type
                    length = type_info.get("len", 20)
                    entry[key] = "".join(
                        random.choices(string.ascii_letters + string.digits, k=length)
                    )
        else:
            # Original implementation
            entry = {
                "url": f"http://test.com/{''.join(random.choices(string.ascii_lowercase, k=10))}",
                "data": "".join(
                    random.choices(string.ascii_letters + string.digits, k=50)
                ),
            }
        data.append(entry)

    return data


async def create_test_data(event, scheduled_md):
    """
    Tests the performance of retrieving unprocessed data using dummy data.
    """
    
    scanner_name = event["name"]
    num_entries = event.get("count", 10)
    random_data = event.get("random-data", False)
    storage_str = event.get("require-storage", "apps::test-data-storage")
    types = event.get("columns", dict())
    generated_data = generate_random_data(num_entries, types)
    matched_storage = web_match_storage(storage_str)
    print("first entry:", generated_data[0].keys())
    print("matched storage length: ", len(matched_storage))
    for st in matched_storage:
        s = st["storage"]
        t1 = time.time()
        d = random.choices(
            generated_data, k=random.randint(num_entries // 10, num_entries)
        )
        s.add_many(d, source="testsource")
        
        t2 = time.time()
        add_time = t2 - t1
        t1 = time.time()
        app_entries_length = s.storage_length()
        t2 = time.time()
        get_len_time = t2 - t1
        
        print(
            "Took: ",
            add_time,
            "to add: ",
            len(d),
            "with storage of length: ",
            app_entries_length,
            "and took: ",
            get_len_time,
            "to fetch the length",
        )
        
        if random_data: generated_data = generate_random_data(num_entries)


async def test_unscanned_entries_retrieval(event, scheduled_md):
    """
    Tests the performance of retrieving unscanned entries.
    """

    scanner_name = event["name"]
    print(f"Testing unscanned entries retrieval for scanner: {scanner_name}")
    t1 = time.time()
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned_entries:
        t2 = time.time()

        if not unscanned_entries:
            print("No unscanned entries found.")
            return

        print(
            f"Took: {t2 - t1:.4f}s to get {len(unscanned_entries)} unscanned entries."
        )
        t1 = time.time()
        entries_by_parent = defaultdict(list)
        for item in unscanned_entries.values():
            entries_by_parent[item["parent"]].append(item["entry"])

        for parent, entries in entries_by_parent.items():
            if not entries:
                continue

            # Assuming the timestamp key is 'c_time'
            entries.sort(key=lambda x: x.get("timestamp", 0))

            # assuming it will always be application storage
            print(f"Parent: {parent.site}", "have", len(entries), "entries")
            # print(f"  First entry (by timestamp): {entries[0]['id']}")
            # print(f"  Last entry (by timestamp): {entries[-1]['id']}")
        t2 = time.time()
        print("Took: ", t2 - t1, "to collect and sort entries")


async def test_multi_storage_retrieval(event, scheduled_md):
    """
    Tests the performance of retrieving unscanned entries from multiple storages.
    """
    scanner_name = event["name"]
    print(f"Testing multi-storage retrieval for scanner: {scanner_name}")
    
    t1 = time.time()
    async with get_multi_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned_entries:
        t2 = time.time()
        # print("**********************")
        # print(unscanned_entries)
        # print("**********************")
        if not unscanned_entries:
            print("No unscanned entries found.")
            return
        
        print(f"Took: {t2 - t1:.4f}s to get {len(unscanned_entries)} unscanned combinations.")
        
        t1 = time.time()
        # Sort by key to be deterministic in logs if needed, though they are usually ordered by generation
        sorted_keys = sorted(unscanned_entries.keys())
        
        for eid in sorted_keys:
            data = unscanned_entries[eid]
            entry_list = data.get("entry", [])
            
            # Construct a summary string
            web_app = entry_list[1]["entry"]
            template = entry_list[0]["entry"]
            print(f"scanning {web_app['site']} with template {template['path']}")
        
        t2 = time.time()
        print(f"Took: {t2 - t1:.4f}s to log entries")


async def add_custom_length_application_storage(event, scheduled_md):
    """
    Creates and adds applications with custom content length to the target storage.
    """
    # Get target storage instance
    target_storage = get_storage()
    
    # Get parameters from event config
    num_apps = event.get("count", 5)  # Number of applications to create
    min_content_length = event.get("min_content_length", 100)  # Minimum content length
    max_content_length = event.get("max_content_length", 5000)  # Maximum content length
    base_domain = event.get("base-domain", "test-app")
    print(
        f"Creating {num_apps} applications with content length between {min_content_length} and {max_content_length}"
    )
    
    apps_to_add = []
    for i in range(num_apps):
        # Generate a random content length within the specified range
        content_length = random.randint(min_content_length, max_content_length)
        status = random.choice([200, 204, 404, 403, 502])
        # Create app data dictionary with custom content length
        app_data = {
            "url": f"https://{i}.{base_domain}:443/",
            "title": f"Test App {i}",
            "content_length": content_length,
            "status_code": status,
            "tech": ["Python", "TestTech"],
            "scheme": "https",
            "host": f"{i}.{base_domain}",
            "input": f"{i}.{base_domain}",
            "timestamp": 0,
            "port": 443
        }
        apps_to_add.append(app_data)

    # Add the applications to target storage in batch
    created_apps = add_apps(target_storage, apps_to_add)
    
    for app in created_apps:
        print(f"Added application {app['site']} with content length: {app['content_length']}")

    print(len(get_uniq_apps(get_storage())), len(get_apps(get_storage())))
    print(f"Successfully added {num_apps} applications with custom content lengths")
