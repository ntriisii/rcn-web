
# RCN Web Server Context for AGENTS

This document provides context on the RCN Web Server environment, available storages, targets, flows, and how to extend functionality using scheduled functions and custom scripts.

## 1. System Overview

The RCN Web Server organizes data into **Targets** and **Web Applications**.
- **Target**: A scope or project containing multiple applications.
- **Web Application**: A specific web application (e.g., `https://example.com`) **the only thing available to you are applications** targets are way of aggregating data in the server only.
- **Storage**: Each application and target has "storages" for specific data types (e.g., `web-apps::app-links`, `web-apps::js-links`, `web-apps::app-flows`, `web-apps::trufflehog-secrets`).

### Key Objects & Helpers

*   **`get_storage()`**: A global helper function that returns the root `TargetStorage` object.
    *   `get_uniq_apps(get_storage())`: Returns a list of unique application dictionaries.
    *   `get_app_by_site(get_storage(), site_name)`: Retrieve an application dictionary by its site name (e.g., `example.com:443`).
    *   `get_storage_create(storage_name)`: Get (or create) a global storage (e.g., `get_storage_create("web-apps")`).

*   **Application Dictionary**: Represents a site.
    *   `app['site']`: The site domain/host.
    *   `get_storage_create(storage_name, parent_id=app['id'])`: Get a storage specific to this app (e.g., `get_storage_create("web-apps::app-links", parent_id=app['id'])`).

*   **Flows**: Network traffic is stored as flows.
    *   `RemoteFlowsAdapter`: Manages access to remote flows from the proxy.
    *   **Headers**: Request and response headers in flows are automatically converted to `MultiDict` objects for easy access (e.g., `flow['request-headers'].getall('Cookie')`).

## 2. Creating Scheduled Functions

Scheduled functions allow you to automate tasks like scanning new URLs, analyzing flows, or performing periodic cleanup. They are defined in Python files and registered with the `@rcn_event()` decorator.

### Structure

A scheduled function must be an `async` function decorated with `@rcn_event()` accepting two arguments:
1.  `event`: A dictionary containing configuration for this event (name, schedule, etc.).
2.  `scheduled_md`: Metadata about the scheduling (last run time, etc.).

### Helper: `get_unprocessed_entries`

Use `rcn_core.data_access.get_unprocessed_entries` with `match_storage_fn=web_match_storage` to efficiently iterate over *new* items in a storage that haven't been processed by this specific scanner yet.

### Examples

#### Example 1: Processing New Links (Storage-Based)

This function checks for new URLs found in applications and prints them.

```python
from rcn_core.log import rlog
from rcn_core.data_access import get_unprocessed_entries, get_storage
from rcn_web.core.utils import web_match_storage
from rcn_core.decorators import rcn_event

@rcn_event()
async def process_new_links(event, scheduled_md):
    scanner_name = event["name"]
    
    # This context manager yields new, unprocessed entries for this scanner
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unprocessed:
        if not unprocessed:
            return

        # 'unprocessed' is a dict where keys are IDs and values contain the entry data
        for item_id, item_data in unprocessed.items():
            entry = item_data['entry'] # The actual data (e.g., the link object)
            
            # Example logic
            url = entry.get('url')
            rlog(f"New link found: {url}")
```

#### Example 2: Analyzing Flows (Flow-Based)

This function inspects new HTTP flows for specific headers.
an HTTP flow is a dict with the following keys (method, path, url, request-headers, request-body, status, response-headers, response-body)

```python
from rcn_core.data_access import get_unprocessed_entries
from rcn_web.core.scope import flow_in_scope
from rcn_web.core.utils import web_match_storage
from rcn_core.decorators import rcn_event

@rcn_event()
async def analyze_headers(event, scheduled_md):
    scanner_name = event["name"]
    
    # Ensure the event in YAML has 'require-storage: flows'
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unprocessed:
        # Extract the flow objects
        flows = [i["entry"] for i in unprocessed.values()]
        if not flows: return

        for flow in flows:
			# checks if the flow in the current scope before processing 
			# required for some events as not to process all the flows.
            if not flow_in_scope(flow): continue
            
            # Access headers (MultiDict)
            headers = flow.get("response-headers")
            if "Server" in headers:
                print(f"Server header: {headers['Server']}")
```

#### Example 3: Processing App Flows from Proxy

This example demonstrates how to retrieve flows by their IDs using `RemoteFlowsAdapter` (which communicates with the proxy) and process them. This is useful when you have flow IDs stored in `app-flows` storage and want to analyze the full request/response content.

```python
from rcn_core.data_access import get_unprocessed_entries, get_storage
from rcn_web.core.utils import web_match_storage, RemoteFlowsAdapter
from rcn_core.decorators import rcn_event

@rcn_event()
async def process_app_flows(event, scheduled_md):
    scanner_name = event["name"]
    
    # Assuming 'require-storage: web-apps::app-flows' in YAML
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unprocessed:
        if not unprocessed: return

        # Collect all flow IDs from the unprocessed entries
        flow_ids = []
        for item_id, item_data in unprocessed.items():
            entry = item_data['entry']
            # Assuming the entry has a 'flow-id' field
            if entry.get('flow-id'):
                flow_ids.append(entry['flow-id'])

        if not flow_ids: return

        # Retrieve full flow objects from the proxy via RemoteFlowsAdapter
        adapter = RemoteFlowsAdapter.get_instance()
        flows = await adapter.get_flows_by_id(flow_ids)
        
        for flow in flows:
            # Process the full flow object
            # flow keys: method, url, request-headers, request-body, status, response-headers, response-body
            
            url = flow.get('url', '')
            status = flow.get('status', 0)
            
            # Example: Check for specific sensitive data in response body
            resp_body = flow.get('response-body', b'')
            if b'API_KEY' in resp_body:
                print(f"Potential API Key found in {url} (Status: {status})")
```

#### Example 4: General Maintenance (Non-Storage Based)

This function demonstrates a general maintenance task that runs periodically without relying on new data in a storage (i.e., it doesn't use `get_unprocessed_entries`).

```python
from rcn_web.core.utils import get_storage, get_uniq_apps
from rcn_core.log import rlog
from rcn_core.decorators import rcn_event

@rcn_event()
async def daily_cleanup_task(event, scheduled_md):
    # This function iterates over all applications and performs a check
    # irrespective of whether they have 'new' data.
    
    st = get_storage()
    if not st: return
    
    for app in get_uniq_apps(st):
        # Example: Log application site
        # rlog(f"Checking app: {app['site']}")
        pass
        
    rlog("Daily cleanup completed.")
```

## 3. Multi-Storage Events & Priority Evals

This section explains how to process entries from multiple storages simultaneously and how to filter/prioritize them using `priority-evals`.

### 3.1 Multi-Storage Events

A **Multi-Storage Event** joins data from multiple storages using a Cartesian Product. This is useful when you need to correlate data between different tables (e.g., matching URLs with their screenshots, or associating findings with their source entries).

**How it works:**
1. The system iterates over entries from the first storage (newest first).
2. For each entry in the first storage, it generates combinations with **all** entries from the remaining storages.
3. The result is a dictionary where each key is a combination ID (e.g., `"1:A:X"`) and each value contains a list of wrapped entries.

**Configuration:**
In your YAML event configuration, specify `require-storage` as a **list** of storage paths:

```yaml
events:
  - name: join-urls-screenshots
    require-storage:
      - web-apps::app-links      # Storage 1 (e1)
      - web-apps::screenshots    # Storage 2 (e2)
    priority-evals:
      - "1 if e1['url'] == e2['original_url'] else -1"
```

**Data Structure:**
When processing multi-storage events, the yielded data structure changes:

```python
# In your processor function:
async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unprocessed:
    for combo_id, item_data in unprocessed.items():
        # item_data['entry'] is a LIST of wrapped entries (one from each storage)
        combo = item_data['entry']
        
        # Access individual entries:
        entry_from_storage1 = combo[0]['entry']  # e1 equivalent
        entry_from_storage2 = combo[1]['entry']  # e2 equivalent
        
        # Access storage objects:
        storage1_obj = combo[0]['storage']
        storage2_obj = combo[1]['storage']
```

### 3.2 Priority Evals

`priority-evals` allows you to filter and score entries/combinations using Python expressions. They are defined in the event configuration as a list of strings.

**How it works:**
1. Each expression is evaluated against the entry/combination.
2. **Negative Result (< 0):** The entry/combination is **filtered out** (discarded).
3. **Positive Result (> 0):** The result is added to the entry's priority score (higher scores are processed first).
4. **Zero (0):** The entry passes through but gets no priority boost.

**Variables Available in Eval:**

| Variable | Description | Example |
| :--- | :--- | :--- |
| `entry` | The data dictionary (single-storage only) | `entry['url']` |
| `e1`, `e2`, `e3` | Entry from Storage 1, 2, 3 (multi-storage) | `e1['url']` |
| `storage` | The storage object (single-storage only) | `storage.storage_name` |
| `s1`, `s2`, `s3` | Storage object from Storage 1, 2, 3 | `s1.storage_name` |
| `parent`, `p1`, `p2`, `p3` | Parent container objects | `p1.name` |

**Examples:**

#### Single-Storage Filtering:
```yaml
# Only process URLs with status 200
priority-evals:
  - "1 if entry.get('status') == 200 else -1"
```

#### Single-Storage Scoring:
```yaml
# Prioritize critical vulnerabilities (score 10) over low (score 1)
priority-evals:
  - "10 if entry.get('severity') == 'critical' else 1"
```

#### Multi-Storage Cross-Table Filtering:
```yaml
# Only keep combinations where the screenshot matches the URL
priority-evals:
  - "1 if e2['original_url'] == e1['url'] else -1"
```

#### Multi-Storage Combined Scoring:
```yaml
# Filter: only keep matching URLs
# Score: bonus 5 points if screenshot has 'logo' in filename
priority-evals:
  - "1 if e2['original_url'] == e1['url'] else -1"
  - "5 if 'logo' in e2.get('filename', '') else 0"
```

**Implementation Note:**
The system executes `priority-evals` inside the Cartesian Product loop for multi-storage events. This means invalid combinations are discarded immediately, saving memory and processing time.

## 4. Structure of Notes

The system uses a flexible note-taking mechanism (annotations) to tag entries, track bugs, and manage tasks. Notes are key-value pairs attached to entries or applications.

### Defined Annotation Categories

**Entries Category**
*   `potential-vuln`: Used to mark an entry as a potential vulnerability.
*   `notes`: General notes or observations about the entry.
*   `run`: Used to specify execution parameters or flags for the entry.

**User Categories**
*   `notify`: Used to notify a user with something in the system, like something is happening or drag the user attention to something.
*   `finding`: This is used to inform the user that something has been found by some of the agents running or by tools.
*   `js-analysis`: Used for annotations and findings resulting from automated JavaScript analysis pipelines.

**ACP Agent Category (`acp-agent-do`)**
*   **Usage**: Used to tell an ACP agent to do something.
*   **Key**: The agent name.
*   **Value**: XML structure containing:
    *   `<instruction>` (mandatory): Should tell the agent what to do.
    *   `<repeat>` (optional): If given should define the period of repeat e.g. 1 second 10 minutes 1 hour.
    *   `<entry>` (optional): Should contain the entry at `<entry_id>` field and the storage that this entry came from in the `<storage>` field.


## 5. Data Exploration & Inspection

When interacting with the server to understand the current state of recon, you have several tools to "view" and "preview" data.

### Filtering with `sql_filter`

The `preview_storage` and `view_storage` tools support an optional `sql_filter` parameter. This allows you to perform efficient server-side filtering using SQLite `WHERE` clause syntax.

- **Purpose**: Use this to narrow down results when a storage contains many entries (e.g., filtering for specific status codes or URL patterns).
- **Syntax**: Standard SQL `WHERE` clause conditions.
    - Examples: `path LIKE '%admin%'`, `status = 200`, `words > 500`.
- **Constraints**: 
    - **Only filtering** is allowed.
    - DO NOT attempt to use `JOIN`, `UNION`, or any data modification keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).
    - The model should use the column names (keys) identified in the storage preview.

### Application Discovery with `view_storage`

When you need to find specific applications or browse through the available ones, use the `view_storage` tool with `storage_name="web-apps"`.

**IMPORTANT Usage Constraints**:
- Use this tool ONLY if no applications were explicitly provided in your initial context.
- Use this tool if the user specifically asks to search or filter through the applications.
- DO NOT use this tool for general "exploration" if you already have target applications assigned to you.

**Parameters**:
- `storage_name`: Must be `"web-apps"`.
- `sql_filter`: (Optional) Standard SQL `WHERE` clause conditions to filter apps.
    - **Available columns**: `site`, `url`, `status_code`, `title`, `technologies`, `cdn`, `content_length`, `scheme`, `tags`, `app_checked`, `disabled`, `created_at`.
    - **Example**: `"status_code = 200 AND technologies LIKE '%React%'"`
- `page`: (Optional) Page number for pagination (starts at 1).
- `limit`: (Optional) Number of results per page (default 20).

**Example Usage**:
- `view_storage(storage_name="web-apps", sql_filter="status_code = 200")`
- `view_storage(storage_name="web-apps", sql_filter="tags LIKE '%todo-important%'", page=2)`


### `preview_storage` vs. `view_storage`

It is crucial to choose the right tool based on the level of detail you need:

| Tool                  | Purpose                       | Output Style                  | When to Use                                                                        |
+|:----------------------|:------------------------------|:------------------------------|:-----------------------------------------------------------------------------------|
+| **`preview_storage`** | High-level metadata overview. | Summary text (counts, names). | To see *what* storages exist, how many items are in them, or a summary of apps.    |
+| **`view_storage`**    | Detailed entry inspection.    | Paginated text table.         | To see the *actual data* (URLs, IP addresses, JS links) inside a specific storage or list applications. |

**Example Usage**:
- `view_storage(storage_name='web-apps', sql_filter="status_code = 200")`
- `view_storage(storage_name='web-apps::app-links', app_id=123, sql_filter="url LIKE '%.php%' AND status = 200")`
- `preview_storage(app_id=123, storage_name='web-apps::js-links', sql_filter="url LIKE '%api%'")`

### Usage Workflow

The primary workflow for interacting with the system is task-driven based on application context and TODOs.

1.  **Context Provision**: You will be provided with a list of applications. For each application, you will receive:
    *   **Preview Text**: High-level metadata about the application's current state (e.g., storage counts).
    *   **TODOs**: A list of specific tasks or notes associated with that application.

2.  **Decision Making**: Based *only* on the provided preview text and TODOs, you must decide on the next course of action.
    *   Analyze the TODOs to understand the goal.
    *   Use the preview text to assess if sufficient data exists to proceed.

3.  **Tool Selection**: Select the most appropriate tool to further your knowledge or execute the task.
    *   **Constraint**: Use as *few tools as possible*. Do not attempt to read everything "just in case."
    *   **Targeted Action**: If a TODO says "check JS files," look specifically at `web-apps::js-links` storage using `view_storage`, rather than listing everything.

4.  **Execution**: Perform the task or investigation using the selected tool.

## 6. Direct Storage Manipulation

While `get_unprocessed_entries` is preferred for scheduled tasks to avoid reprocessing data, you can also interact with storages directly for bulk reading and writing.

### Reading Data: `.get()`

The `.get()` method retrieves all entries currently stored in a specific storage for the current application context.

```python
from rcn_web.core.utils import get_storage, get_app_by_site
from rcn_core.storage.bases import get_storage_create

st = get_storage()
app = get_app_by_site(st, "example.com")
app_links_storage = get_storage_create("web-apps::app-links", parent_id=app['id'])

# Retrieve all links for this app
all_links = app_links_storage.get()
for link in all_links:
    print(link['url'])
```

### Writing Data: `.add_many(entries, source="default")`

To add new data to a storage, use the `.add_many()` method. It takes a list of dictionaries, where each dictionary represents an entry.

*   **`entries`**: A list of dicts. Keys should match the storage schema (if it exists) or they will be dynamically added as columns.
*   **`source`**: A string indicating the origin of the data (e.g., `crawl`, `fuzz`, `manual`).

```python
from rcn_web.core.utils import get_storage, get_app_by_site
from rcn_core.storage.bases import get_storage_create

st = get_storage()
app = get_app_by_site(st, "example.com")
js_links_storage = get_storage_create("web-apps::js-links", parent_id=app['id'])

new_js_files = [
    {"url": "https://example.com/static/js/main.js", "size": 1024},
    {"url": "https://example.com/static/js/vendor.js", "size": 5400}
]

# Add entries to storage
js_links_storage.add_many(new_js_files, source="my_custom_script")
```

**Note:** `add_many` automatically handles ID generation and timestamping for each entry.

## 7. Strict API Reference (DO NOT HALLUCINATE)

Use ONLY the following methods on the respective objects. Do NOT invent new methods (e.g., `find`, `filter`).

### Global Helpers
*   **`get_storage()`**: Returns the root `TargetStorage` object.
*   **`get_uniq_apps(st)`**: Returns a list of unique application dictionaries.
*   **`get_app_by_site(st, site_name)`**: Get application dictionary by URL/Site.
*   **`get_storage_create(name, parent_id=None)`**: Get or create a storage object. Use `parent_id` for app-level storages.

### `AbstractDataStorage` (The storage object)
*   **`st.get()`**: Get ALL entries.
*   **`st.add_many(entries: List[dict], source: str)`**: Add new entries.
*   **`st.add_annotation(entry_id, key, value)`**: Add an annotation to a specific entry.
*   **`st.get_annotations()`**: Get all annotations for this storage.

**There are NO `find()`, `search()`, or `filter()` methods.** You must use `.get()` to retrieve all data and then filter it using standard Python list comprehensions.

## 8. Scanning & Fuzzing Automation

These tools abstract the process of scheduling tasks and will automatically wait for and poll for results.

**VERY IMPORTANT** These tools don't store the Flows content on the server the scanning or fuzzing are done on a seperate server, please don't use the  
### Primary Tool: `perform_scanning`

Triggers a Nuclei scan on the target application.

**Parameters**:
- `app_name`: Application name (site name) to target.
- `config_xml`: The XML configuration block for Nuclei (see structure below).

**Example Usage**:
```python
perform_scanning(
    app_name="example.com",
    config_xml="<scanning><base-url>https://example.com/</base-url><templates>http/exposed-panels/</templates></scanning>"
)
```

### Primary Tool: `perform_fuzzing`

Triggers a FFUF fuzzing task on the target application (ONLY used when the fuzzing list is large else use the `ewp_send_request_to_server**).

**VERY IMPORTANT** if the wordlist is going to be automatically generated (using a function or a wordlist you manually generate) and it is around 1000 to 2000 elements you must use `ewp_send_request_to_server` tool instead, please take HEED to this note as this is very important to me. 

**Parameters**:
- `app_name`: Application name (site name) to target.
- `config_xml`: The XML configuration block for FFUF (see structure below).

**Example Usage**:
```python
perform_fuzzing(
    app_name="example.com",
    config_xml="<fuzzing><base-url>https://example.com/api</base-url><wordlist>https://example.com/wordlist.txt</wordlist></fuzzing>"
)
```

### Configuration XML Structures

#### For Nuclei Scans (`perform_scanning`)
```xml
<scanning>
    <base-url>
https://example.com/target1
https://example.com/target2
    </base-url>
    <templates>path/to/template.yaml,http/cves/2023/CVE-2023-XXXX.yaml</templates>
    <!-- Optional: <args> additional nuclei args </args> -->
</scanning>
```
**Note on `base-url`**: This can be a single URL or a **newline-separated list of URLs**. For scanning, this list (referenced internally as `l1`) defines all targets to be scanned.

**Note on templates**: Local templates should be stored in the `nuclei-template/` directory at the project root. Please note that files in this directory may have been generated for other scans and are not necessarily related to your current task.

#### For Fuzzing (`perform_fuzzing`)
```xml
<fuzzing>
    <base-url>
https://example.com/api1
https://example.com/api2
    </base-url>
    <wordlist>https://example.com/wordlist.txt</wordlist>
    <wordlist>local/path/to/wordlist.txt</wordlist>
    <dynamic-code>
def generate_wordlist():
    return ['admin', 'backup', 'config']
    </dynamic-code>
    <!-- Optional: <args> additional ffuf args </args> -->
</fuzzing>
```
**Note on `base-url` and `wordlist`**:
- `<base-url>` can be a **newline-separated list of URLs** (referenced internally as `l1`).
- The collected wordlist (from files and dynamic code) is referenced internally as `l2`.
- The fuzzing process typically uses these as `l1` and `l2` for the underlying `rr` (request-response) command.

**Note on wordlists**: Local wordlists should be stored in the `wordlists/` directory at the project root. Please note that files in this directory may have been generated for other scans and are not necessarily related to your current task.

**Note**: When using `dynamic-code`, the code must define a `generate_wordlist()` function that returns a list of strings.


# Comprehensive Org-mode (.req.org) Automation & Scripting

The system uses Org-mode files (`.req.org`) to define HTTP requests and interact with applications. These files allow you to chain requests (e.g., login before action), extract data, and use Python logic to generate dynamic content.

**Avoid Metadata Footers:** whenever editing the req.org file, Never use the `(End of file - total X lines)` footer from the `read` tool in your `oldString`. It is a UI element, not file content.
*   **The "Context Wrap" Pattern:** To append to a file, capture the **last 2-3 unique lines** of the file and use them as your `oldString`. In your `newString`, repeat those lines exactly and then add your new content.

## 1. Agent Guidelines & Efficiency

*   **Context First**: When tasked with working on a specific request or endpoint, **ALWAYS** read the specific `.req.org` file and the `globals.yaml` in the same directory first. These contain 90% of the context you need (variables, auth tokens, helper functions).
*   **Minimal Tool Usage**: Do not use `glob` or `ls` to explore the file system unless the request is obscure or the file location is unknown. Rely on the file paths provided in the prompt or the standard structure.
*   **Single Batch Read**: Try to read the `.req.org`, `globals.yaml`, and `script.py` in a single turn if possible to load the full context immediately.

## 2. Core Components

*   **`.req.org` Files**: Define the HTTP requests and functionality. Each top-level heading represents a distinct operation.
*   **`globals.yaml`**: Defines shared variables (users, cookies, base URLs) available to all requests in the directory.
*   **`script.py`**: Defines Python functions available globally to all requests in the directory.
*   **`app_structure.org`**: Located at the root of an application's repeater directory (e.g., `repeater/github.com:443/app_structure.org`). It documents the known paths, endpoints, and overall architecture of the application.

## 3. URL and Host Precedence

When generating request content, follow these rules to determine the target URL and `Host` header:
1.  **`globals.yaml`**: First, check for a `url` definition in the `globals.yaml` file within the same directory. If found, **DO NOT** redefine it in the node.
2.  **Current File Context**: If and ONLY If no URL is defined in `globals.yaml` (or the file is missing), you must define a `url` variable in the `!ewp-yaml` block of the node.
3.  **Forbidden Metadata**: NEVER use the `# :server-url:` comment metadata format. The system resolves the URL automatically from the `url` variable.

You should prioritize the identified URL for both the request target and the `Host` header. Do not overthink these values; if you are unsure, provide a reasonable default based on these rules, as the user can easily adjust them later.

## 4. Anatomy of a Request Node

A node is an Org heading that contains variables, python logic (org-babale source blocks to include functions), and one or more HTTP requests.
HTTP requests are defined using #+begin_src !ewp-request and only there can be one main request, other requests are helper requests that we use to extract data from their responses to include in other requests or the main request.

**Flexibility**: The node content is not restricted to variables and requests. You can include plain text descriptions, observations, or other Org-mode source blocks. These serve as notes for the user and are ignored by the proxy execution engine.

**CRITICAL Constraint**: NEVER generate `:PROPERTIES:` blocks (like `:ID:`, `:url:`) when creating nodes. These are handled automatically by the system. If you include them, it will cause duplication or errors.

### Flow Metadata & Filtering

Every flow captured from an Org node execution includes metadata about the origin of the request. You can use this metadata to filter flows related to specific files or directories.

**Key Metadata Fields**:
- `node-file` (direct: `node_file`): The absolute path to the `.req.org` file that sent the request.
- `node-id` (direct: `node_id`): The ID of the Org node.
- `proxy-detector` (direct: `proxy_detector`): A unique ID generated for each execution of a node.

**Usage in Filtering**:
When calling `ewp_get_flows_matching`, you can target these fields directly or via the `metadata` object. Direct access is preferred for brevity.

*Example: Find all flows sent from a specific execution (detector):*
- `ewp_get_flows_matching(filter_eval="proxy_detector == 'prxy_abc123'")`

*Example: Find all flows sent from a specific file:*
- `ewp_get_flows_matching(filter_eval="node_file == '/path/to/my_node.req.org'")`

### Creating Nodes (`ewp_create_org_node`)

When you need to create a NEW functionality or operation in a `.req.org` file, you **MUST** use the `ewp_create_org_node` tool. This is the **ONLY** authorized way to create new nodes.

**Arguments**:
- `org_heading` (str): The name of the operation (e.g., 'Delete User').
- `org_content` (str): The body of the node (variables, python blocks, requests).
- `filename` (str): Absolute path to the `.req.org` file.
- `line_number` (int): The line where the node should be inserted.

**Usage Rules**:
- To **edit** an existing node, continue using the standard `edit` command.
- Do **NOT** include the `* ` prefix in `org_heading`; the tool handles it.
- Do **NOT** generate `:PROPERTIES:` blocks; the system adds them automatically.

### 1. Variables (`node-vars`)
Define local variables using `!ewp-yaml :type node-vars`.
```yaml
#+begin_src !ewp-yaml :type node-vars
username: "admin"
target_user: "{{user1::username}}"
base_path: "/api/v1"
endpoints: `{["docs", "openapi.json", "users.json"]}1`
full_path: "{{base_path}}/{{endpoints}}" # going to use endpoints one by one

#+end_src
```

### 2. Python Logic (`python`) & `VARS`
You can define helper functions in a `#+begin_src python` block.
*   **`VARS`**: A globally available dictionary containing all variables (`globals`, `node-vars`, and dynamic run-time values).
*   **Usage**: You can access `VARS` inside these blocks or inline code.

```python
#+begin_src python
def get_auth_header():
    # VARS['api_token'] comes from globals.yaml or node-vars
    token = VARS.get('api_token', 'default_token')
    return f"Bearer {token}"

def calculate_signature():
    # Example of using a value from a previous request
    # Note: VARS access is only valid inside python blocks or `{}` interpolation
    nonce = VARS.get('nonce', rand_str(10))
    return hashlib.sha256(nonce.encode()).hexdigest()
#+end_src
```

**Interpolation Syntax**:
*   `{{variable}}`: Simple string replacement from `node-vars` or `globals`.
*   `` `{python_code}` ``: Evaluate Python code inline.

### 4. Fuzzing & Iteration Strategies

You can control how variables iterate by appending a **Level Number** (e.g., `1`, `2`) to the interpolation block.

*   **Pitchfork (Sync)**: Variables with the **same level** (e.g., `{{a}}1`, `{{b}}1`) iterate together.
*   **ClusterBomb (Product)**: Variables with **different levels** (e.g., `{{a}}1`, `{{b}}2`) iterate as a Cartesian product.
*   **Sniper (Level Xs)**: Appending `s` to a level number (e.g., `3s`) enables "Sniper" mode. For each iteration of the sniper variable, only the placeholders with a matching index (using `{{var::<index> default}}`) are replaced with the current value. All other placeholders for that variable revert to their `default` value. This allows testing multiple positions sequentially using a single generator.
*   **Python Generators**: Use list/set comprehensions inside `` `{}` `` to generate dynamic wordlists.
*   **Nested Interpolation**: You can use variables inside other variables in `node-vars`.

**Example: Advanced Sync & generation (Pitchfork, ClusterBomb, Sniper)**
This scenario demonstrates how different levels interact to create complex fuzzing patterns.

**Setup**:
#+begin_src !ewp-yaml
url: "http://epam.lvh.me"

 # Level 1: Synchronized with other Level 1s (Pitchfork)
names: `{i for i in range(3)}1`

 # Level 2: Cartesian Product with Level 1 (ClusterBomb)
 # Each 'name' from L1 will be tested with every 'path' from L2
paths: `{i for i in range(3)}2`

 # Level 3s: Sequential positioning (Sniper)
 # For each combination of L1 and L2, this variable will be injected
 # into positions 1, 2, and 3 one by one, while others stay default.
sniper_v: `{"val " + str(i) for i in range(3)}3s`
#+end_src

#+begin_src !ewp-request
GET /{{paths}} HTTP/1.1
\# :server-url: http://{{names}}.epam.lvh.me
Host: epam.lvh.me
Testing-Header: test
Sniper-Pos-1: {{sniper_v::1 first}}
Sniper-Pos-2: {{sniper_v::2 second}}
Sniper-Pos-3: {{sniper_v::2 third}}
Sniper-Pos-4: {{sniper_v::3 fouth}}

#+end_src

**Iteration Breakdown**:
The total number of requests is calculated as: `(Count L1) * (Count L2) * (Count L3s * Positions)`.
In this example: `3 (names) * 3 (paths) * (3 values * 3 positions) = 81 requests`.

1.  **Pitchfork (Level 1)**: `names` iterates from 0 to 2.
2.  **ClusterBomb (Level 2)**: For `names=0`, `paths` iterates 0, 1, 2. (Same for `names=1`, `names=2`).
3.  **Sniper (Level 3s)**: For each `names`/`paths` pair (e.g., `0/0`):
    - **Iteration 3s.1** (Value "val 0"):
      - `Sniper-Pos-1`: `val 0` (matches index 1)
      - `Sniper-Pos-2`: `second` (default)
      - `Sniper-Pos-3`: `third` (default)
    - **Iteration 3s.2** (Value "val 1"):
      - `Sniper-Pos-1`: `first` (default)
      - `Sniper-Pos-2`: `val 1` (matches index 2)
      - `Sniper-Pos-3`: `val 1` (matches index 2)
    - ... and so on for all 3 values across all 3 positions.

**Specific Example (from captured flows)**:
A node defined with:
#+begin_src !ewp-yaml
names: `{i for i in range(3)}1`
paths: `{i for i in range(3)}2`
#+end_src
#+begin_src !ewp-request
GET /{{paths}} HTTP/1.1
/# :server-url: http://{{names}}.epam.lvh.me
#+end_src
Will generate requests like:
- `http://0.epam.lvh.me/0`
- `http://0.epam.lvh.me/1`
- `http://0.epam.lvh.me/2`
- `http://1.epam.lvh.me/0`
- ... and so on (Total 9 requests).

### 5. The Request (`!ewp-request`)
The raw HTTP request.
*   **Main Request**: Mark with `:main t`. There MUST be ONLY ONE main request per node. This is the primary test you want to perform.
*   **Helper (Non-Main) Requests**: Requests *without* the `:main t` flag. These are used EXCLUSIVELY for data extraction (e.g., getting a CSRF token or a session cookie). They MUST have an `:id <name>` to be referenced.

**Generation Best Practices**:
- **Prefer Python**: Use inline Python `` `{}` `` or Python blocks for dynamic generation (e.g., loops for multiple paths).
- **Reuse with Variables**: If data is used in multiple places (headers, body, path), define it once in a variable (via `node-vars` or a Python block) and interpolate the variable.

```http
#+begin_src !ewp-request :main t
GET /api/create HTTP/1.1
Host: api.example.com
Authorization: `{get_auth_header()}`
X-Signature: `{calculate_signature()}`
Content-Type: application/json

{"id": "`{rand_str(8)}`", "name": "test"}
#+end_src
```

### 2. Python Logic (`python`) & `VARS`
You can define helper functions in a `#+begin_src python` block.
*   **`VARS`**: A globally available dictionary containing all variables (`globals`, `node-vars`, and dynamic run-time values).
*   **Usage**: You can access `VARS` inside these blocks or inline code.

```python
#+begin_src python
def get_auth_header():
    # VARS['api_token'] comes from globals.yaml or node-vars
    token = VARS.get('api_token', 'default_token')
    return f"Bearer {token}"

def calculate_signature():
    # Example of using a value from a previous request
    # Note: VARS access is only valid inside python blocks or `{}` interpolation
    nonce = VARS.get('nonce', rand_str(10))
    return hashlib.sha256(nonce.encode()).hexdigest()
#+end_src
```

**Interpolation Syntax**:
*   `{{variable}}`: Simple string replacement from `node-vars` or `globals`.
*   `` `{python_code}` ``: Evaluate Python code inline.

### 4. Fuzzing & Iteration Strategies

You can control how variables iterate by appending a **Level Number** (e.g., `1`, `2`) to the interpolation block.

*   **Pitchfork (Sync)**: Variables with the **same level** (e.g., `{{a}}1`, `{{b}}1`) iterate together.
*   **ClusterBomb (Product)**: Variables with **different levels** (e.g., `{{a}}1`, `{{b}}2`) iterate as a Cartesian product.
*   **Nested Interpolation**: You can use variables inside other variables in `node-vars`.

**Example: Advanced Sync & generation**
This scenario demonstrates:
1.  **Nested Variables**: `test-header-value` uses `test_inner_header`.
2.  **Level 1**: Iterates a list of IDs generated by Python.
3.  **Level 2**: Synchronized iteration of `var2` and `var4` (Pitchfork).
4.  **Level 3s (Sniper)**: Special Static/Keyed access. For each iteration, only placeholders matching the current index (e.g., `{{var::1 ...}}`) receive the value; others use their provided default.

```org
#+begin_src !ewp-yaml
url: "http://localhost:8000"
test_inner_header: another test in the inner header
# Nested Variable
test-header-value: "testing freaking shit {{test_inner_header}}"

# Level 1: Python Generator
var1: `{i for i in range(3)}1`

# Level 2: Sync Generators
var2: `{i for i in range(3)}2`
var4: `{rand_str(3) for i in range(3)}2`

# Level 3s: Special Static/Keyed access (sniper attack)
var3s: `{i for i in range(3)}3s`
#+end_src

#+begin_src !ewp-request
GET / HTTP/1.1
Host: localhost
testing-header: {{test-header-value}} 
shitting-shit: mother fucker
var1: this is {{var1}}
var2: this is {{var2}}
var4: this is {{var4}}
var2s-1: this is {{var3s first}}
var2s-2: this is {{var3s second}}
var2s-3: this is {{var3s third}}
#+end_src
```

### 5. The Request (`!ewp-request`)
The raw HTTP request.
*   **Main Request**: Mark with `:main t`. There MUST be ONLY ONE main request per node. This is the primary test you want to perform.
*   **Helper (Non-Main) Requests**: Requests *without* the `:main t` flag. These are used EXCLUSIVELY for data extraction (e.g., getting a CSRF token or a session cookie). They MUST have an `:id <name>` to be referenced.
*   **Request Metadata**: Key request details are defined as **comments** immediately following the request line. Specifically, use `# :server-url: scheme://host:port`. This allows the proxy to know exactly where to send the request without parsing the Host header deeply or relying on DNS.

**Generation Best Practices**:
- **Prefer Python**: Use inline Python `` `{}` `` or Python blocks for dynamic generation (e.g., loops for multiple paths).
- **Reuse with Variables**: If data is used in multiple places (headers, body, path), define it once in a variable (via `node-vars` or a Python block) and interpolate the variable.

```http
#+begin_src !ewp-request :main t
GET /api/create HTTP/1.1
# :server-url: https://api.example.com:443
Host: api.example.com
Authorization: `{get_auth_header()}`
X-Signature: `{calculate_signature()}`
Content-Type: application/json

{"id": "`{rand_str(8)}`", "name": "test"}
#+end_src

#+begin_src !ewp-request :main t
{{verb}} {{path}} HTTP/1.1
# :server-url: https://api.target.com:443
Host: api.target.com
Content-Type: application/json

{"id": "{{uid}}", "u": "{{user}}", "p": "{{pass}}"}
#+end_src
```

### 5. The Request (`!ewp-request`)
The raw HTTP request.
*   **Main Request**: Mark with `:main t`. There MUST be ONLY ONE main request per node. This is the primary test you want to perform.
*   **Helper (Non-Main) Requests**: Requests *without* the `:main t` flag. These are used EXCLUSIVELY for data extraction (e.g., getting a CSRF token or a session cookie). They MUST have an `:id <name>` to be referenced.
*   **Request Metadata**: Key request details are defined as **comments** immediately following the request line. Specifically, use `# :server-url: scheme://host:port`. This allows the proxy to know exactly where to send the request without parsing the Host header deeply or relying on DNS.

**Generation Best Practices**:
- **Prefer Python**: Use inline Python `` `{}` `` or Python blocks for dynamic generation (e.g., loops for multiple paths).
- **Reuse with Variables**: If data is used in multiple places (headers, body, path), define it once in a variable (via `node-vars` or a Python block) and interpolate the variable.

```http
#+begin_src !ewp-request :main t
GET /api/create HTTP/1.1
Host: api.example.com
Authorization: `{get_auth_header()}`
X-Signature: `{calculate_signature()}`
Content-Type: application/json

{"id": "`{rand_str(8)}`", "name": "test"}
#+end_src
```


## 5. Automation & Extraction API (`intp_scope`)

These functions are available in `script.py`, `python` blocks, and inline `` `{}` `` expressions.

### Data Extraction (Cross-Node)
To extract data, you must reference the **Request ID** defined in the source block (e.g., `#+begin_src !ewp-request :id my-req`).

| Function | Return Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `resp_xpath(id, xpath)` | `list[str]` | Extract text/values from HTML/XML. | `` `{resp_xpath('login-req', '//input[@name="csrf"]/@value')[0]}` `` |
| `resp_json(id)` | `dict` \| `list` | Parse response body as JSON. | `` `{resp_json('api-req')['data']['id']}` `` |
| `resp_jq(id, filter)` | `dict` \| `list` \| `str` | Filter JSON using JQ syntax. | `` `{resp_jq('api-req', '.users[0].id')}` `` |
| `resp_hdr(id, name)` | `str` | Get a specific response header. | `` `{resp_hdr('login-req', 'Set-Cookie')}` `` |
| `resp_raw(id)` | `str` | Raw response body. | `` `{resp_raw('debug-req')}` `` |
| `form_csrf(name)` | `str` | Auto-extract token from form in previous response. | `` `{form_csrf('csrf_token')}` `` |
| `csrf_request_resp(node)`| `str` | Get response of request named `csrf-request`. | `` `{csrf_request_resp(VARS['__node'])}` `` |

### Request Inspection
| Function | Return Type | Description |
| :--- | :--- | :--- |
| `req_raw(id)` | `str` | Raw request body. |
| `req_headers(id)` | `dict` | Request headers. |
| `req_cookies(id)` | `dict` | Request cookies. |
| `req_url(id)` | `str` | Full URL. |
| `req_path(id)` | `str` | URL Path. |

### Utilities
*   `rand_str(length)` -> `str`: Generate random alphanumeric string.
*   `rand_int(max)` -> `int`: Generate random integer.
*   `timestamp_now()` -> `int`: Current Unix timestamp.
*   `wordlist_read(url_or_path)` -> `list[str]`: Read lines from a URL or local file path.

## 6. Multiple Requests in One Node (Complex Chaining)

You can define multiple requests within a single Org node (heading). This is standard for flows requiring setup steps (CSRF extraction, authentication) before the main action.

*   **Helper Requests**: Any `!ewp-request` block *without* `:main t`. Must have an `:id`.
*   **Main Request**: The `!ewp-request` block *with* `:main t`. Only one per node.
*   **Execution Order**: The order of requests within a node matters. The proxy executes them sequentially as they appear in the file. For example, if a node has two helper requests followed by a main request and then another helper request, the proxy will send them in that exact order (Helper 1 -> Helper 2 -> Main -> Helper 3). This is crucial for chains where a request depends on data extracted from a preceding one.

**Example: Login flow with CSRF extraction**

```org
* Login and Fetch User Data

# 1. Helper: Get the login page to extract CSRF token
#+begin_src !ewp-request :id req-login-page
GET /login HTTP/1.1
# :scheme: https
# :server-host: target.com
# :server-port: 443
Host: target.com
#+end_src

# 2. Python: Extract the token using the helper's ID
#+begin_src python
def get_csrf_token():
    # Extracts value of <input name="csrf"> from the response of 'req-login-page'
    return resp_xpath('req-login-page', '//input[@name="csrf"]/@value')[0]
#+end_src

# 3. Main: Perform the login
#+begin_src !ewp-request :main t :id req-login-action
POST /login/authenticate HTTP/1.1
# :scheme: https
# :server-host: target.com
# :server-port: 443
Host: target.com
Content-Type: application/x-www-form-urlencoded

csrf_token=`{get_csrf_token()}`&username={{user}}&password={{pass}}
#+end_src
```

## 7. Global Variables (`globals.yaml`)

Define users and environment data here.

```yaml
globals:
  users: [user1, user2]

user1:
  username: "admin"
  password: "password123"
  session: "PHPSESSID=..."
```

Access via `{{user1::username}}` or `VARS['user1']['username']`.


## 8. Request Execution Policy
- **Creation vs. Execution:** When asked to "create", "add", "define", or "write" requests, nodes, or test cases, ONLY perform the file modifications. 
    - To **CREATE** a new node, use the `ewp_create_org_node` tool.
    - To **EDIT** an existing node, use the standard `edit` command.
- **Explicit Trigger:** NEVER execute requests (e.g., using `ewp_send_request_to_server` or `perform_fuzzing` or any other tools) unless explicitly commanded to "run", "execute", "test", or "start the scan" ONLY use those tools when the user didn't request for anything to be created inside the req.org or scripts files.
- **Default State:** Always assume the user wants to review or further modify created content before it is sent to a target.

## 9. Maintaining Application Structure (`app_structure.org`)

The `app_structure.org` file is your primary reference for understanding the application's layout and functionality. It is your responsibility to keep this file accurate and up-to-date.

**When to Read**:
- **Initial Context**: Always read this file when starting work on a new application or directory to understand existing functionality and avoid redundant testing.

**When to Update**:
- **New Paths**: If you add a new functionality or discover a new URI path in a `.req.org` node that is not yet documented, you must update `app_structure.org` to include it. Note: This refers to high-level paths/endpoints, not individual request nodes.
- **Functionality Changes**: If you refine your understanding of an endpoint's behavior or discover new features, adjust the structure accordingly.

This ensures a persistent, high-level map of the target application that evolves alongside your testing efforts.

**what to include**:
for each discovered path please make headings that seperate the 

# Emacs Web Proxy (EWP) MCP Server

## 1. Core Workflow

1.  **Strategy Generation**: Based on the context provided in the prompt (HTTP request details and notes), the AI generates a Python generator function (`fn_request_generator`).
2.  **Execution**: The AI calls `ewp_send_request_to_server` with the generated function.
3.  **Analysis**: The proxy executes the requests, captures flows, and returns a summary. The AI then uses flow inspection tools to analyze results and save findings.

## 2. EWP Tools & Technical Specifications

### `ewp_send_request_to_server`
Sends raw Org-mode content to the proxy for execution. This is the primary tool for performing exploitation and fuzzing.

**Arguments**:
- `org_content` (str): The complete Org-mode source containing nodes, variables, and requests.
- `rationale` (str): A short explanation of the testing strategy.

### `ewp_send_org_http_content_to_server`
Sends a Python function generator to the proxy for execution.

**Arguments**:
- `fn` (str): The complete Python code for `fn_request_generator`.
- `rationale` (str): A short explanation of the testing strategy.

### `ewp_add_execution_summary`
Saves test findings and insights back to the Org node notes. Use this to ensure progress is tracked and redundant tests are avoided.

**Example**:
`ewp_add_execution_summary(summary="IDOR confirmed on /api/user/105. Status 200 returned full profile.")`

# Tool Selection Guidelines

Use the following framework to decide which tool to employ for a given task. This applies to both general server automation and interactive proxy tasks.

## 1. Scenarios for `perform_fuzzing` or `perform_scanning`
*   **Large Wordlists**: Use these tools when the task involves fuzzing with large wordlists (thousands or tens of thousands of entries).
*   **Nuclei Templates**: Use `perform_scanning` when you need to run multiple Nuclei templates targeting specific CVEs.

## 2. Scenarios for `ewp_send_request_to_server`
*   **Chained Requests**: Use when you need to fetch a token (CSRF, session) before sending the target request.
*   **Org-native Features**: When leveraging `node-vars`, directory `globals.yaml`, or complex interpolation.
*   **Multi-Node Attacks**: When the attack requires multiple sequential steps defined as Org nodes.

## 3. Scenarios for `ewp_send_org_http_content_to_server`
*   **Complex Python Logic**: Use when the request generation requires advanced Python control flow or data manipulation that is easier expressed as a generator function.

# Flow Inspection Tools
Use `ewp_get_flows_matching`, or `ewp_get_flow` to retrieve and analyze results from the proxy.

### `ewp_get_flow`
Retrieves a specific flow by its ID with support for advanced filtering, partial retrieval, and intelligent summarization.

**Key Features**:
- **Reflective Summarization**: By default, if the response body is large (>10k), `get_flow` automatically searches for "reflections" (parameters from the request found in the response). It prunes irrelevant parts of HTML/JSON to provide a concise view of how your input influenced the output.
- **Server-Side Filtering**: Filters (`jq_filter`, `xpath_filter`) are executed directly on the proxy server. This is highly efficient for analyzing large responses as it only sends the relevant matches back to you, saving bandwidth and context window space.
- **Part Selection**: You can specify exactly which components of the flow you need using the `parts` parameter. Available parts include:
    - `method`: The HTTP method (e.g., GET, POST).
    - `url`: The full URL.
    - `path`: The path component of the URL.
    - `status`: The response status code.
    - `request-headers`: The request headers.
    - `response-headers`: The response headers.
    - `request-body`: The raw request body.
    - `response-body`: The raw response body.

**Parameters**:
- `flow_id` (str): The unique timestamp-based ID of the flow.
- `parts` (list, optional): Components to return (e.g., `['method', 'request-headers', 'request-body']`).
- `jq_filter` (str, optional): A `jq` filter string for JSON response bodies. Bypasses automatic summarization.
- `xpath_filter` (str, optional): An XPath 1.0 expression for HTML/XML response bodies. Bypasses automatic summarization.

**Nuanced Examples**:
- **Standard Inspection**: `get_flow(flow_id="1737400000.123")` -> Returns headers and a summarized/reflective body.
- **Targeted Header Check**: `get_flow(flow_id="1737400000.123", parts=['response-headers'])` -> Returns ONLY the response headers.
- **Extracting Data from JSON**: `get_flow(flow_id="1737400000.123", jq_filter='.items[] | {id: .id, name: .name}')` -> Returns a compact, pretty-printed JSON list of items.
- **Extracting HTML Content**: `get_flow(flow_id="1737400000.123", xpath_filter='//form//input[@name="csrf"]/@value')` -> Directly extracts the CSRF token value.
- **Combined Parts & Filter**: `get_flow(flow_id="1737400000.123", parts=['request-headers', 'response-body'], jq_filter='.status')` -> Returns the request headers (including the full request line: method, path, and HTTP version) and only the 'status' field from the response body.
- **Detailed Headers**: `get_flow(flow_id="1737400000.123", parts=['response-headers'])` -> Returns the full response status line (HTTP version, status code, and reason phrase) followed by all response headers.

**Note**: When a filter is applied, the `response-body` part (if requested or defaulted) will contain the filtered result rather than the original content.

**Example for `ewp_get_flows_matching`**:
`ewp_get_flows_matching(filter_eval="(entry['status'] == 200) & (entry['metadata']['desc'].contains('SQLi'))")**



# Tips for handling user requests 
those tips are here to make you distinguish between tool use and how to use them, **IMPORTANT** those tips take prioirty over any other note I have so please follow them carefully when trying to answer the user requests:
- when the request originates from files like *.req.org or script.py org globals.yaml, please try to use as less tools as possible.
- when the user asks for recent flows, please don't try to check for matching flows or check for check for apps, or flows from the rcn-web, do this **ONLY** if the request is still not fulfuilled or cannot be fulfilled without them, this is to save context and provide contnet to the user faster.




