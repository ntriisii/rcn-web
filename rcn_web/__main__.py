import os
import sys
import asyncio
import uvicorn
import argparse
import concurrent.futures
import ruamel.yaml.error as yml_err

from contextlib import asynccontextmanager

import rcn_core.globals
from rcn_core.parse_yaml import load_files
from rcn_core.log import rlog
from rcn_core.storage.target_storage import MultiTargetStorage

# Data needs to be loaded before APP
def init_config():
    # Attempt to load rcn_exports from the project root
    exports_pkg = None
    try:
        import rcn_exports
        exports_pkg = rcn_exports
    except ImportError:
        pass

    try:
        load_files(exports=exports_pkg)
    except yml_err.YAMLError as error:
        rlog(f"there was an error while loading the yaml files {error}", level="error")

if __name__ == "__main__":
    init_config()

# Import app after config loading
from .main import app

if __name__ == "__main__":
    server_yaml_config = rcn_core.globals.YAML_FILE_CONTENT
    
    host_default = "localhost"
    port_default = 8023
    
    # Try to get log level from config
    try:
        log_level_default = server_yaml_config.get("server-config", {}).get("fastapi-log-level", "info")
    except:
        log_level_default = "info"

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "target_dir",
        type=str,
        help="The directory where the rcn target is located (required positional argument)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=host_default,
        help=f"Host to run the server on (default: {host_default})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=port_default,
        help=f"Port to run the server on (default: {port_default})",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=log_level_default,
        help=f"Log level for uvicorn (default: {log_level_default})",
    )

    args = parser.parse_args()

    rcn_core.globals.TARGET_DIR = os.path.abspath(args.target_dir)

    # Initialize Storage
    storage_obj = MultiTargetStorage(rcn_core.globals.TARGET_DIR)
    rcn_core.globals.TARGET_STORAGE = storage_obj

    loop = rcn_core.globals.EVENT_LOOP

    try:
        config = uvicorn.Config(
            app=app, host=args.host, port=args.port, loop=loop, log_level=args.log_level
        )
        server = uvicorn.Server(config=config)
        loop.run_until_complete(server.serve())

    except KeyboardInterrupt:
        asyncio.run(storage_obj.dump_data())
        if rcn_core.globals.POOL_EXECUTOR:
            rcn_core.globals.POOL_EXECUTOR.shutdown()
        
        observers = (
            rcn_core.globals.SERVER_WATCHDOG_OBSERVERS
            + rcn_core.globals.PROXY_WATCHDOG_OBSERVERS
            + rcn_core.globals.PY_WATCHDOG_OBSERVERS
        )

        for i in observers:
            try:
                i.stop()
                i.join()
            except:
                pass
