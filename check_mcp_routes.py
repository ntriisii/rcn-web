import os
import sys

# Set up path to include local packages
python_root = os.path.expanduser("~/programming-projects/python/rcn-web/")
sys.path.insert(0, python_root)
sys.path.insert(0, os.path.expanduser("~/programming-projects/python/rcn-core/"))

from rcn_web.main import app

print("Listing all registered routes:")
for route in app.routes:
    # Handle standard routes
    if hasattr(route, "path") and hasattr(route, "methods"):
        print(f"{route.methods} {route.path} -> {route.name}")
    # Handle included routers
    elif hasattr(route, "routes"):
        for sub_route in route.routes:
            print(f"{sub_route.methods} {sub_route.path} -> {sub_route.name}")
