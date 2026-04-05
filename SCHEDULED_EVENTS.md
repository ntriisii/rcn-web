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

### Processing Unprocessed Entries
The most common pattern is processing new data that has not yet been seen by a specific "scanner". This is handled via the `get_unprocessed_entries` context manager.

When an event specifies a `require-storage` in its YAML configuration, the scheduler collects all relevant storage instances. The handler then iterates over the entries that are "unprocessed" for that specific event.

### Annotations
Instead of modifying raw data entries (which are passed as read-only dictionaries), analysis results should be stored as **Annotations**. Annotations are linked to an entry and allow for multi-stage processing.

To add an annotation, use the global utility:
```python
from rcn_core.storage.bases import add_annotation

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

Events are defined in automation YAML files. **IMPORTANT**: For an automation file to be active, it must be included in the `includes` section of the master configuration.

### YAML Schema
```yaml
time-events:
  - function: py_my_handler     # Prefix function name with py_
    enabled: true               # Enable/disable the task
    every: 10s                  # Scheduling frequency (e.g., 30s, 1h)
    require-storage: "entities" # The storage type to process
    min-entries: 1              # Minimum unprocessed entries to trigger
    max-entries: 100            # Maximum entries to process per run
    custom_param: "value"       # Custom parameters passed in the 'event' dict
```

*   **`every`**: Defines the execution frequency.
*   **`require-storage`**: Tells the scheduler which storage to collect data from. The handler will receive these as unprocessed entries.
*   **`min-entries` / `max-entries`**: Control the volume of data processed in a single run.

---

## 4. Implementation Example

```python
from rcn_core.decorators import rcn_event
from rcn_core.data_access import get_unprocessed_entries
from rcn_core.storage.bases import add_annotation

@rcn_event()
async def process_data_entries(event, *args):
    scanner_name = event.get("name")
    
    # get_unprocessed_entries yields a dict of:
    # { id: {"entry": dict, "storage": storage_obj, "parent": parent_obj} }
    async with get_unprocessed_entries(scanner_name, event) as unscanned:
        for item in unscanned.values():
            entry = item["entry"]     # The raw data dictionary
            storage = item["storage"] # The storage instance
            parent = item["parent"]   # The parent entity (e.g., target)

            # Perform analysis
            result = my_analysis_logic(entry)
            
            # Store results as an annotation
            add_annotation(
                entry_id=entry["id"],
                storage_name=storage.storage_name,
                key="my-result",
                value=result,
                parent_id=parent["id"]
            )
```
