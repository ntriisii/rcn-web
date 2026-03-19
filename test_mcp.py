import time
import requests
import json

BASE_URL = "http://localhost:8023/new-target"
APP_NAME = "portal.staging8.ns.epam.lvh.me:80"


def trigger_scan():
    print(f"Triggering scan for {APP_NAME}...")
    payload = {
        "action": "scan_app",
        "params": {
            "app_name": APP_NAME,
            "config_xml": f"<config><target>https://{APP_NAME}</target></config>",
        },
    }
    resp = requests.post(f"{BASE_URL}/mcp/action", json=payload)
    print("Trigger response:", resp.status_code, resp.text)

    if resp.status_code != 200:
        return None

    data = resp.json()
    return data.get("source_id")


def check_results(source_id):
    print(f"Polling results for {source_id}...")
    payload = {
        "app_site": APP_NAME,
        "source_name": source_id,
        "min_timestamp": time.time() - 3600,
        "scan_type": "scanning",
    }

    for i in range(10):  # Try 10 times
        resp = requests.post(f"{BASE_URL}/mcp/check_scan_results", json=payload)
        print(f"Attempt {i + 1} status:", resp.status_code)
        if resp.status_code == 200:
            print("Response:", resp.text)
            if "No new scan results found yet." not in resp.text:
                print("Got results!")
                return
        else:
            print("Error response:", resp.text)
        time.sleep(5)
    print("No results after polling.")


if __name__ == "__main__":
    source_id = trigger_scan()
    if source_id:
        check_results(source_id)
