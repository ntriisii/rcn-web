# Scheduled Events & Background Orchestration

Scheduled events are asynchronous Python functions triggered periodically based on configuration. They are the primary mechanism for automated background processing, discovery, and data analysis pipelines.

---

## 1. Core Concepts

### The `@rcn_event` Decorator
All event handlers must be registered using the `@rcn_event()` decorator to be discoverable by the orchestration engine.

### Function Signature
Every event handler **MUST** be an `async` function. The first argument is the `event` configuration dictionary. While a second `scheduled_md` argument exists in the system, it is managed internally and should not be used for logic implementation.

```python
from rcn_core.decorators import rcn_event

@rcn_event()
async def my_scheduled_handler(event, *args):
    # event: Dictionary containing YAML configuration parameters
    ...
```

---

## 2. Advanced Data Processing Patterns

### A. Processing Unprocessed Entries
This is the standard pattern for data discovery and enrichment. It ensures that each entry in a storage is handled exactly once by a specific task.

When `require-storage` is specified in YAML, the scheduler identifies all matching storages. The `get_unprocessed_entries` context manager then provides a dictionary of items that haven't been "seen" by the task's unique `name`.

```python
async with get_unprocessed_entries(scanner_name, event) as items:
    for item in items.values():
        entry = item["entry"]     # The raw data dictionary
        storage = item["storage"] # The storage instance
        parent = item["parent"]   # The parent entity dictionary
```

### B. Processing Annotations (Metadata Processing)
Annotations are metadata "tags" attached to entries. Processing annotations allows for creating complex analysis pipelines where one task's finding triggers another task's action.

To process only new annotations with a specific key, use `get_unprocessed_annotations`:

```python
from rcn_core.data_access import get_unprocessed_annotations

# Processes only new annotations where key == "analysis-needed"
async with get_unprocessed_annotations("analysis-needed", scanner_name, event) as unscanned:
    for item in unscanned.values():
        annotation = item["entry"]           # The annotation dictionary
        ref_storage = item["storage"]        # The storage the annotation is on
        parent = item["parent"]              # The parent entity
        
        # Access the annotation value
        task_description = annotation["value"]
```

### C. The Discovery Pipeline (Producer-Consumer)
A "Producer" event gathers data and creates new entries. A "Consumer" event (using `require-storage`) picks up those new entries. This creates a reactive chain of automation.

---

## 3. Configuration (YAML)

Events are defined in automation YAML files. **IMPORTANT**: For an automation file to be active, it must be explicitly included in the `includes` section of the master configuration (e.g., `server-config.yaml`).

### YAML Schema & Parameters
```yaml
time-events:
  - function: py_my_handler     # Prefix function name with py_
    enabled: true               # Enable/disable the task
    every: 10s                  # Scheduling frequency (e.g., 30s, 1h, 1d)
    single-run: false           # If true, the event runs once then disables
    require-storage: "entities" # The storage type to process
    min-entries: 1              # Minimum unprocessed entries to trigger
    max-entries: 100            # Maximum entries to process per run
    name: "my-task-id"          # Unique identifier for state tracking
    config_option: "value"      # Custom parameters passed in the 'event' dict
```

*   **`every`**: Execution frequency. Supports time suffixes like `s`, `m`, `h`, `d`.
*   **`require-storage`**: Specifies which storage to collect data from.
*   **`name`**: Critical for tracking progress. It acts as the "fingerprint" that prevents re-processing the same data.

### Configuration Overlays
You can provide default configurations for a group of events using a `config:` block.

```yaml
my-automation-group:
  config:
    every: 5m
    max-entries: 50
  events:
    - function: py_handler_one
      name: "task-1"
    - function: py_handler_two
      name: "task-2"
      every: 1h  # Overrides the group default
```

### D. Operational Synchronization (Semaphores)
Handlers use **Storage Metadata Flags** to coordinate execution state across multiple events. This prevents redundant processing and handles "lock" states between independent tasks. Common flags include `[task]-running`, `[task]-finished`, and `[task]-last-check-time`.

---

## 4. Operational Coordination: Semaphores & Error Recovery

To ensure robust execution, handlers often implement a "Locking" pattern using storage-level metadata. This is critical for tasks that are expensive or must not overlap.

### The Locking Pattern
By checking for a "running" flag before starting and clearing it on completion (or failure), handlers can ensure they only run once across the entire project structure.

```python
@rcn_event()
async def coordinated_task(event, *args):
    async with get_unprocessed_entries(event["name"], event) as items:
        for item in items.values():
            entry = item["entry"]
            parent = item["parent"]
            
            # 1. Check for Semaphores (Locks)
            if parent.storage_md_get("my-task-finished"): continue
            if parent.storage_md_get("my-task-running"): continue
            
            # 2. Set the Lock
            parent.storage_md_set("my-task-running", True)
            parent.storage_md_set("my-task-started", datetime.now().timestamp())
            
            try:
                # 3. Perform Logic...
                await perform_heavy_logic(entry)
                
                # 4. Record Success
                parent.storage_md_set("my-task-finished", True)
            except Exception as e:
                # 5. Handle Failures & Reset Locks
                # This ensures the task can be retried on next execution
                raise e
            finally:
                # Always clear the lock
                parent.storage_md_set("my-task-running", False)
```

### F. Cross-Storage Context (Enrichment)
Handlers can retrieve data from **multiple storages** simultaneously. While processing a primary entry, a handler can query unrelated storages (e.g., matching IPs against Domains) to create a richer context for its analysis.

---

## 5. Advanced Implementation: Cross-Referencing & Enrichment

Complex handlers often need to look outside their primary storage to make informed decisions. This is done by directly retrieving other storages via `get_storage().get_storage_create("storage-name")`.

### Pattern: The Contextual Enricher
This pattern is used to combine data from different discovery sources to provide a unified finding.

```python
from rcn_core.data_access import get_storage

@rcn_event()
async def enrichment_handler(event, *args):
    # Primary storage we are processing
    scanner_name = event.get("name")
    
    # 1. Access a secondary storage for cross-referencing
    # e.g., We are processing 'Findings' but want to check against 'Inventory'
    inventory_st = get_storage().get_storage_create("inventory")
    inventory_data = {i["id"]: i for i in inventory_st.get()}
    
    async with get_unprocessed_entries(scanner_name, event) as items:
        for item in items.values():
            entry = item["entry"]
            
            # 2. Perform cross-storage lookup
            related_info = inventory_data.get(entry.get("related_id"))
            
            if related_info:
                # 3. Enrich the finding with data from the secondary storage
                add_annotation(
                    entry_id=entry["id"],
                    storage_name=item["storage"].storage_name,
                    key="enriched-context",
                    value=related_info["metadata"],
                    parent_id=item["parent"]["id"]
                )
```

### G. Flow Delegation (Modular Execution)
Heavy or complex logic is often abstracted into **Flows** (via `RCN_FLOWS`). An event handler acts as a thin orchestrator that retrieves data, instantiates a specific flow, and awaits its completion. This ensures modularity and easy testing of complex logic.

---

## 6. Advanced Implementation: Flow Delegation

For tasks involving complex, multi-stage logic, handlers delegate work to specialized **Flow** objects. This pattern is essential for logic that requires its own state management or external resource handling.

### Pattern: The Flow Orchestrator
This pattern allows the event system to trigger complex, predefined workflows stored in the `RCN_FLOWS` registry.

```python
from rcn_core.globals import RCN_FLOWS

@rcn_event()
async def flow_orchestrator_handler(event, *args):
    # 1. Identify the flow to run (can be defined in YAML)
    flow_name = event.get("flow", "default-flow")
    flow_fn = RCN_FLOWS.get(flow_name)
    
    if not flow_fn:
        return
    
    async with get_unprocessed_entries(event["name"], event) as items:
        for item in items.values():
            entry = item["entry"]
            
            # 2. Instantiate the Flow
            flow = flow_fn()
            
            # 3. Pass data from the entry and event config
            flow.set_data(entry)
            flow.set_config(event)
            
            try:
                # 4. Run the Flow asynchronously
                result = await flow.run()
                
                # 5. Handle output...
                process_flow_results(result)
            except Exception as e:
                # 6. Errors are raised back to the scheduler
                raise e
```

---

## 7. Full Pipeline Case Study: Discovery to Validation

This example shows a three-stage pipeline: **Discovery** -> **AI Annotation** -> **Functional Validation**.

### Stage 1: Discovery (The Producer)
**YAML Config**:
```yaml
- function: py_discover_new_items
  every: 1h
  name: "initial-discovery"
```

**Python Handler**:
```python
from rcn_core.storage.bases import get_storage_create

@rcn_event()
async def discover_new_items(event, *args):
    # Gathering data from an external source...
    new_data = [{"name": "item_1"}, {"name": "item_2"}]
    
    # Store in a dedicated storage
    # This will trigger any events requiring "raw-items"
    st = get_storage_create("raw-items")
    st.add_many(new_data)
```

### Stage 2: AI Annotation (The Analyzer)
**YAML Config**:
```yaml
- function: py_analyze_items
  every: 10s
  require-storage: "raw-items"
  name: "ai-analyzer"
```

**Python Handler**:
```python
from rcn_core.storage.bases import add_annotation

@rcn_event()
async def analyze_items(event, *args):
    async with get_unprocessed_entries(event["name"], event) as items:
        for item in items.values():
            entry = item["entry"]
            
            # Tag the item for deep-dive validation
            add_annotation(
                entry_id=entry["id"],
                storage_name=item["storage"].storage_name,
                key="needs-validation",
                value="Check integrity of " + entry["name"],
                parent_id=item["parent"]["id"]
            )
```

### Stage 3: Functional Validation (The Annotation Consumer)
**YAML Config**:
```yaml
- function: py_validate_annotations
  every: 30s
  require-storage: "raw-items::annotations"
  name: "validator"
```

**Python Handler**:
```python
@rcn_event()
async def validate_annotations(event, *args):
    # Process only annotations with key="needs-validation"
    async with get_unprocessed_annotations("needs-validation", event["name"], event) as items:
        for item in items.values():
            annotation = item["entry"]
            parent_id = item["parent"]["id"]
            
            # Perform actual validation...
            success = await run_validation(annotation["value"])
            
            # Record final verdict as a NEW annotation on the original entry
            add_annotation(
                entry_id=annotation["entry_id"], # Link back to original entry
                storage_name=item["storage"].storage_name,
                key="validation-verdict",
                value="Success" if success else "Failed",
                parent_id=parent_id
            )
```
