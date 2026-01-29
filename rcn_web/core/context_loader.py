import sys
import inspect
import importlib
import pkgutil
from typing import Dict, Any

import rcn_core.globals
from rcn_core.log import rlog

# Import base modules that should be scanned
# We scan these packages recursively
import rcn_web.core.events
import rcn_web.automation
import rcn_web.scanning
import rcn_web.viewers.emacs
import pentest_utils.web.rcn_helpers

def register_web_context():
    """
    Dynamically discovers and registers web-specific functions into the global YAML context.
    This eliminates the need to manually update the context list in main.py.
    """
    
    context_updates: Dict[str, Any] = {}
    
    # 1. Define packages/modules to scan
    # For packages, we will iterate over their submodules
    packages_to_scan = [
        rcn_web.automation,
        rcn_web.scanning,
        rcn_web.viewers.emacs,
    ]
    
    # Single modules to scan directly
    modules_to_scan = [
        rcn_web.core.events,
        rcn_web.core.remote_flow_processor,
        pentest_utils.web.rcn_helpers,
    ]

    # Helper to process a module
    def scan_module(module):
        try:
            for name, obj in inspect.getmembers(module):
                # We only want functions defined in the module (or explicitly exported ones if needed)
                # But mostly we want functions defined in the project files.
                if inspect.isfunction(obj) or inspect.iscoroutinefunction(obj):
                    # Check if function belongs to the rcn_web or pentest_utils package (approximate check)
                    # to avoid registering imports like 'json', 'sys', etc.
                    if hasattr(obj, '__module__') and (
                        obj.__module__.startswith('rcn_web') or 
                        obj.__module__.startswith('pentest_utils')
                    ):
                        context_updates[name] = obj
                        
                        # Special handling for functions named like 'py_something'
                        # YAML parser expects 'py_something' in YAML to map to 'something' in context (strips py_)
                        # But if the python function ITSELF is named 'py_something', 
                        # we might want to expose it as 'something' too, to match the stripped YAML name.
                        if name.startswith("py_"):
                            short_name = name[3:]
                            if short_name:
                                context_updates[short_name] = obj
                                
        except Exception as e:
            rlog(f"Error scanning module {module}: {e}", level="warn")

    # Scan recursive packages
    for package in packages_to_scan:
        if hasattr(package, "__path__"):
            # It's a package, iterate modules
            for _, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
                try:
                    module = importlib.import_module(name)
                    scan_module(module)
                except ImportError as e:
                    rlog(f"Failed to import module {name}: {e}", level="warn")
        else:
            # It's just a module
            scan_module(package)

    # Scan individual modules
    for module in modules_to_scan:
        scan_module(module)

    # Apply updates to global context
    rcn_core.globals.YAML_CONTEXT.update(context_updates)
    rlog(f"Registered {len(context_updates)} functions to YAML context.", level="info")
