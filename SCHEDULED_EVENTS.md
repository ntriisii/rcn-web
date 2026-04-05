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

### C. Data Enrichment (Annotation)
Handlers often follow a "Read-Analyze-Tag" pattern. They read raw data, perform analysis (e.g., pattern matching, external tool execution), and "annotate" the original entry with metadata rather than modifying it directly.

### D. Hierarchical Orchestration
Events can be chained. One event's output (e.g., creating a new entry in a sub-storage) often acts as the trigger for the next event in the pipeline.

---

## 3. Configuration (YAML)

Events are orchestrated via YAML files, typically located in `~/.config/rcn-web/`.

### The Event Schema
A typical event entry in a YAML file looks like this:

```yaml
time-events:
  - function: py_my_scheduled_handler  # Mapping to the Python function
    enabled: true                      # Activation toggle
    interval: 60                       # Run every 60 seconds
    single-run: false                  # Set to true for one-time initialization
    custom_param: "value"              # Passed into the 'event' dict
```

*   **`function`**: The name of the Python function. By convention, it is prefixed with `py_` in YAML, which the loader strips to find the decorated function.
*   **`interval`**: The frequency of execution in seconds.
*   **`single-run`**: If true, the event runs once and is then disabled.

### Configuration Aggregation (`includes`)
The system uses a recursive include mechanism to manage complex configurations. A master file (e.g., `server-config.yaml`) can aggregate settings from multiple sources:

```yaml
includes:
  - "~/.config/rcn-web/data-processing.yaml"
  - "~/.config/rcn-web/maintenance/*.yaml"  # Glob patterns supported
```

---

## 4. Creating a New Event: Step-by-Step

To create and enable a new scheduled event:

### Step 1: Implement the Handler
Define your `async` function in a Python module within the project (e.g., in a `scanning/` or `core/` subdirectory).

```python
from rcn_core.decorators import rcn_event
from rcn_core.data_access import get_unprocessed_entries

@rcn_event()
async def process_new_entries(event, scheduled_md):
    # 1. Define the scope of work
    scanner_name = event.get("name", "generic-processor")
    
    # 2. Iterate over new, unseen data
    async with get_unprocessed_entries(scanner_name, event) as entries:
        for item in entries.values():
            entry = item["entry"]
            # 3. Perform the work
            result = perform_analysis(entry)
            # 4. Record the finding/annotation
            entry.add_annotation("processed-result", result)
```

### Step 2: Register in YAML
Add the entry to your `time-events.yaml` or a dedicated include file.

```yaml
- function: py_process_new_entries
  enabled: true
  interval: 300
  name: "my-custom-processor"
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
