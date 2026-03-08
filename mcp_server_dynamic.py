#!/home/ahmed/programming-projects/python/rcn-web/.venv/bin/python3
import os
from rcn_core.mcp.generic_client import start_mcp_client

if __name__ == "__main__":
    start_mcp_client(
        server_url=os.environ.get("RCN_SERVER_URL", "http://localhost:8023"),
        mcp_name="RCN Web Data Explorer",
    )
