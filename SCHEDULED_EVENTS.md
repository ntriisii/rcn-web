# Scheduled Events & Background Orchestration

Scheduled events are asynchronous Python functions triggered periodically based on configuration. They are the primary mechanism for automated background processing and data analysis.

---

## 1. Core Concepts

### The `@rcn_event` Decorator
All event handlers must be registered using the `@rcn_event()` decorator to be discoverable by the orchestration engine.

### Function Signature
Every event handler **MUST** be an `async` function. The first argument is always the `event` configuration dictionary.

```python
from rcn_core.decorators import rcn_event

@rcn_event()
async def my_scheduled_handler(event, *args):
    # event: Dictionary containing YAML configuration parameters
    ...
```

---

## 2. Data Processing Patterns

Scheduled events generally follow one of several core architectural patterns:

### A. The Unprocessed Entry Loop
This is the most common pattern for data enrichment. The event handler iterates over new data that has not yet been processed by this specific task.

When `require-storage` is specified in YAML, the scheduler identifies all matching storages. The `get_unprocessed_entries` context manager then provides a dictionary of items that haven't been tagged by the event's unique `name`.

### B. The Discovery Pipeline (Producer-Consumer)
One event acts as a **Producer**, gathering data and creating new entries in a storage. A subsequent event acts as a **Consumer**, picking up those new entries for specialized analysis.

### C. Initializer Tasks (`single-run`)
Tasks that perform one-time setup or bootstrap logic for a new entity. These use the `single-run: true` flag in YAML to ensure they only fire once.

### D. Batch Processing
By using `max-entries` and `min-entries`, events can perform "trickle processing"—handling small, manageable chunks of data over time to prevent system resource exhaustion during massive data ingestions.

### E. Annotations & Data Tagging
Instead of modifying raw data entries (which are passed as read-only dictionaries), analysis results should be stored as **Annotations**. Annotations are linked to an entry and allow for multi-stage processing.

To add an annotation, use the global utility:
```python
from rcn_core.storage.bases import add_annotation

# Add a discovery finding or analysis result to an existing entry
add_annotation(
    entry_id=entry["id"],
    storage_name=storage.storage_name,
    key="analysis-tag",
    value="result-data",
    parent_id=parent_id
)
```

---

## 3. Configuration (YAML)

Events are defined in automation YAML files. **IMPORTANT**: For an automation file to be active, it must be included in the `includes` section of the master configuration (e.g., `server-config.yaml`).

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
    name: "my-task"             # Unique identifier for state tracking
    custom_param: "value"       # Custom parameters passed in the 'event' dict
```

*   **`every`**: Execution frequency. Supports time suffixes like `s`, `m`, `h`, `d`.
*   **`require-storage`**: Tells the scheduler which storage to collect data from. The handler will receive these as unprocessed entries.
*   **`min-entries` / `max-entries`**: Control the volume of data processed in a single run.
*   **`name`**: Critical for `get_unprocessed_entries`. It acts as the "fingerprint" of the scanner to track which entries have already been seen.

### Configuration Overlays
You can provide default configurations for a group of events using a `config:` block. This is useful for passing shared parameters like API keys or base prompts.

```yaml
my-automation-group:
  config:
    every: 300
    custom_flag: true
  events:
    - function: py_handler_one
    - function: py_handler_two
```

---

## 4. Implementation Variations

### Variation 1: Basic Enrichment (Consumer)
Processes raw data and adds a simple tag.

```python
from rcn_core.decorators import rcn_event
from rcn_core.data_access import get_unprocessed_entries
from rcn_core.storage.bases import add_annotation

@rcn_event()
async def tag_new_entries(event, *args):
    scanner_name = event.get("name")
    
    # Iterate over { id: {"entry": dict, "storage": storage_obj, "parent": parent_obj} }
    async with get_unprocessed_entries(scanner_name, event) as items:
        for item in items.values():
            entry = item["entry"]
            storage = item["storage"]
            parent = item["parent"]

            # Perform logic...
            add_annotation(
                entry_id=entry["id"],
                storage_name=storage.storage_name,
                key="my-tag",
                value="processed",
                parent_id=parent["id"]
            )
```

### Variation 2: Data Discovery (Producer)
Reads entries from one storage and creates new ones in another.

```python
from rcn_core.storage.bases import get_storage_create

@rcn_event()
async def discover_new_entities(event, *args):
    scanner_name = event.get("name")
    
    async with get_unprocessed_entries(scanner_name, event) as items:
        for item in items.values():
            entry = item["entry"]
            parent = item["parent"]
            
            # Find something new...
            findings = extract_logic(entry)
            
            # Add new data to a dedicated discovery storage
            sub_storage = get_storage_create("discoveries", parent_id=parent["id"])
            sub_storage.add_many([{"data": f} for f in findings])
```

### Variation 3: Initializer (Bootstrapping)
Sets up initial state when a new parent entity is created.

```python
@rcn_event()
async def handle_bootstrapping(event, *args):
    # This task likely uses 'single-run: true' in YAML
    async with get_unprocessed_entries(event["name"], event) as items:
        for item in items.values():
            entity = item["entry"]
            # Perform expensive one-time setup
            await setup_entity_logic(entity)
```
