# Scheduled Events & Background Orchestration

This document describes the architecture, creation, and configuration of scheduled events within the RCN platform. The system is designed for modular, stateful, and reactive background data processing.

---

## 1. Core Concepts

Scheduled events are asynchronous Python functions that run periodically or reactively based on data availability. They are the primary mechanism for automating long-running tasks, data enrichment, and system maintenance.

### The `@rcn_event` Decorator
All event handlers must be registered using the `@rcn_event()` decorator. This registration makes the function discoverable by the YAML orchestration engine.

### Function Signature
Every event handler **MUST** be an `async` function and accept exactly two arguments:

```python
@rcn_event()
async def my_scheduled_handler(event, scheduled_md):
    # Implementation logic here
    ...
```

1.  **`event` (Configuration Context)**: A dictionary containing the parameters defined in the YAML configuration for this specific task. It carries the "what" and "how" of the execution (e.g., limits, custom flags, identifiers).
2.  **`scheduled_md` (State Context)**: A persistent dictionary managed by the orchestration engine. It serves as the "memory" for the task, tracking progress (e.g., last processed index, timestamps, run counts) across executions to ensure resumability and prevent redundant work.

---

## 2. General Purpose & Patterns

Events serve several general architectural purposes beyond specific domain logic:

### A. Incremental Data Processing
Instead of processing entire datasets, handlers typically use an **unprocessed entry pattern**. This ensures that each piece of data is handled exactly once by a specific processor, even across system restarts.

### B. State Management & Resumability
By leveraging `scheduled_md`, handlers can resume large tasks from the exact point of interruption. This is critical for tasks that trickle-process data over hours or days.

### C. Data Enrichment (Annotations)
Handlers often follow a "Read-Analyze-Tag" pattern using **Annotations**. Instead of modifying original entries, handlers "tag" them with metadata or analysis results. This allows for multi-stage processing where subsequent handlers filter for specific annotation tags to perform deeper analysis.

### D. Hierarchical Orchestration
Events can be chained. One event's output (e.g., creating a new entry in a sub-storage or adding an annotation) often acts as the trigger for the next event in the pipeline.

### E. Data-Storage Mapping
The system supports a powerful mapping mechanism where an event can request a specific type of storage (e.g., `entities::annotations`) and the orchestration engine will automatically identify all matching storage instances across different parent entities. This allows a single event handler to process data across the entire project structure without knowing the specific hierarchy in advance.

---

## 3. Configuration (YAML)

Events are orchestrated via YAML files, typically located in `~/.config/rcn-web/`.

### The Event Schema
A typical event entry in a YAML file looks like this:

```yaml
time-events:
  - function: py_my_scheduled_handler  # Mapping to the Python function
    enabled: true                      # Activation toggle
    every: 60                          # Run every 60 seconds
    single-run: false                  # Set to true for one-time initialization
    require-storage: "entities"        # Wait for data in this storage
    min-entries: 1                     # Only fire if at least 1 entry is found
    max-entries: 100                   # Process at most 100 entries per run
    custom_param: "value"              # Passed into the 'event' dict
```

*   **`function`**: The name of the Python function. By convention, it is prefixed with `py_` in YAML, which the loader strips to find the decorated function.
*   **`every`**: The frequency of execution in seconds. Note: The scheduler uses `every`, not `interval`.
*   **`single-run`**: If true, the event runs once and is then disabled.
*   **`require-storage`**: A core orchestration parameter. If set, the scheduler will only fire the event if the specified storage has entries. The orchestration engine uses a mapping function (e.g., `web_match_storage`) to find matching storages across all parent entities.
*   **`min-entries`**: The minimum number of unprocessed entries required in the storage for the event to fire.
*   **`max-entries`**: A cap on the number of entries the handler should process in a single execution, useful for chunking large datasets.

### Execution Models: Push vs. Pull
The RCN platform supports two ways of triggering scheduled events:
1.  **Pull (Polling)**: The scheduler checks every `every` seconds if conditions (like `min-entries`) are met and fires the event.
2.  **Push (Reactive)**: When new data is added to a storage via system-wide utilities (e.g., `add_many`), the system automatically schedules the relevant consumer events to run immediately, ensuring minimal latency between data discovery and processing.

### Configuration Aggregation (`includes`)
The system uses a recursive include mechanism to manage complex configurations. **IMPORTANT**: For any YAML configuration or automation file to be active, it **must** be explicitly listed in the `includes` section of the master configuration file (e.g., `server-config.yaml`).

```yaml
includes:
  - "~/.config/rcn-web/data-processing.yaml"
  - "~/.config/rcn-web/maintenance/*.yaml"  # Glob patterns supported
```

---

## 4. Creating a New Event: Step-by-Step

To create and enable a new scheduled event:

### Step 1: Implement the Handler
Define your `async` function in a Python module within the project.

```python
from rcn_core.decorators import rcn_event
from rcn_core.data_access import get_unprocessed_entries

@rcn_event()
async def process_new_entries(event, scheduled_md):
    # 1. Define the scanner name for state tracking
    # This acts as a unique ID for the handler's progress in each storage
    scanner_name = event.get("name", "my-processor")
    
    # 2. Iterate over unprocessed data
    # get_unprocessed_entries automatically pulls from the storage 
    # defined in 'require-storage' in the YAML configuration.
    async with get_unprocessed_entries(scanner_name, event) as entries:
        for item in entries.values():
            entry = item["entry"]
            
            # 3. Work with Annotations
            # Check if this entry already has specific processing markers
            if entry.storage_md_get("processed-flag"):
                continue

            # 4. Perform the work and tag the result
            result = perform_analysis(entry)
            
            # Annotations allow you to add findings without modifying raw data
            # They can be used to trigger subsequent event handlers
            entry.add_annotation("processed-result", result)
            entry.storage_md_set("processed-flag", True)
```

### Step 2: Register in YAML
Add the entry to an automation file that is included in the master `server-config.yaml`.

```yaml
- function: py_process_new_entries
  enabled: true
  every: 300
  name: "my-custom-processor"
  require-storage: "entities"
  min-entries: 5
```

---

## 5. General Examples

### Example 1: Periodic Maintenance
An event that runs once an hour to clean up temporary resources or rotate logs.
*   **Pattern**: Uses `scheduled_md["last-run"]` to check if enough time has passed since the last successful execution.

### Example 2: Continuous Discovery
An event that monitors a "seed" storage and generates new entries in a "work" storage.
*   **Pattern**: Acts as a producer in a producer-consumer chain.

### Example 3: Deep Analysis (Incremental)
An event that processes a large static dataset in small chunks to avoid system overhead.
*   **Pattern**: Uses `scheduled_md["last-index"]` to process 100 entries at a time, updating the index after each successful batch.
