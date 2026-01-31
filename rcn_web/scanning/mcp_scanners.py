
import json
import sys
import aiohttp
import asyncio

from rcn_core.data_access import get_storage
from rcn_core.data_access import get_unprocessed_annotations, get_unprocessed_entries
from rcn_web.core.utils import mcp_server_user_interaction, web_match_storage
from rcn_core.storage.bases import get_storage_create, add_annotation as global_add_annotation
from rcn_core.decorators import rcn_event


@rcn_event()
async def mcp_ai_tag_apps_for_scanning(event, scheduled_md):
    """
    Prompt the AI to tag applications for Nuclei scanning and Fuzzing.
    The AI should output XML with specific tags and potentially generate templates/wordlists.
    """
    
    scanner_name = event["name"]
    
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        if not unscanned: return
        
        apps = [i["entry"] for i in unscanned.values()]
        if not apps: return
        
        ai_payload = """I have a list of applications that I need you to analyze and tag for specific scanning and fuzzing tasks.
        
You need to produce an XML output containing instructions for Nuclei scanning and Fuzzing.

1. **Nuclei Scanning**:
   - Root tag: `<scanning>`
   - Mandatory inner tag: `<base-url>` (the URL to scan)
   - Inner tag: `<templates>` (comma-separated list of template paths or URLs)
   
   **Template Sources**:
   a. **Web Search**: Use `google_web_search` to find existing Nuclei templates that match the application's technologies (e.g., specific CMS, framework, or known vulnerability).
   b. **Generation**: If you identify a suspicious behavior or a potential custom vulnerability, GENERATE a Nuclei template yourself.
      - **CRITICAL**: Save any generated template to the `nuclei-template/` directory at the project root.
      - Use `write_file` to save the template (e.g., `nuclei-template/my-custom-cve.yaml`).
      - In the `<templates>` tag, refer to this local path.

   **Template Generation Guide**:
   If you generate a template, ensure it follows the standard Nuclei YAML syntax.
   **Example Nuclei Output**:
   <scanning>
       <base-url>https://example.com/path/to/endpoint</base-url>
       <templates>nuclei-template/generated-auth-bypass.yaml,http/cves/2023/CVE-2023-XXXX.yaml</templates>
   </scanning>

2. **Fuzzing**:
   - Root tag: `<fuzzing>`
   - Mandatory inner tag: `<base-url>` (the URL to fuzz)
   - Inner tags for wordlists:
   
   **Wordlist Sources**:
   a. **Web Search/Existing**: Search for appropriate wordlists (e.g., SecLists, FuzzDB, PayloadAllTheThings) on GitHub. You can use the raw URL directly in the tag.
   b. **Generation**: Generate a custom wordlist based on the application context.
      - **CRITICAL**: Save generated wordlists to the `wordlists/` directory at the project root.
      - Use `write_file` to save it (e.g., `wordlists/custom-api-paths.txt`).
   c. **Dynamic Generation**: Provide the actual self-contained Python code inside the `<dynamic-code>` tag. This code must define a function named `generate_wordlist` that returns a list of strings (the wordlist entries).
      - Example: `<dynamic-code>def generate_wordlist(): return ['user' + str(i) for i in range(100)]</dynamic-code>`

   **Example Fuzzing Output**:
   <fuzzing>
       <base-url>https://example.com/api</base-url>
       <wordlist>https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/common.txt</wordlist>
       <wordlist>wordlists/custom-generated.txt</wordlist>
       <dynamic-code>
def generate_wordlist():
    # your logic here
    return ['admin', 'backup', 'config']
</dynamic-code>
   </fuzzing>

**Applications to Analyze**:
"""
        for app in apps:
            ai_payload += f"\nAPP ID: {app['id']}\n"
            ai_payload += json.dumps(app, default=str, indent=2)
            ai_payload += "\n-------------------\n"
        
        ai_payload += "\n**Instructions**: For each application above, analyze its technologies and context, you can view storages from applications to get more context, then generate the appropriate XML tags for scanning and fuzzing as described. Use the provided tools (web search, file writing) to fetch or create the necessary resources."
        ai_payload += "\n\n**CRITICAL ACTION**: Use the `add_annotation` tool to persist your tagging."
        ai_payload += "\n- For fuzzing instructions, use `key='tool-fuzzing'` and set `value` to your generated `<fuzzing>...</fuzzing>` XML."
        ai_payload += "\n- For scanning instructions, use `key='tool-scanning'` and set `value` to your generated `<scanning>...</scanning>` XML."
        
        response = await mcp_server_user_interaction(ai_payload, msg_type="ai-todo")
        
        if response and response.get('finished'):
             print(f"Sent {len(apps)} apps for AI tagging.")
        elif response is False or response is None:
             print("No terminal available or error sending data.")


@rcn_event()
async def mcp_interactive_ai_process_todo_notes(event, scheduled_md):
    """
    Collects application annotations with 'todo' keys and sends them to an AI service via WebSocket.
    Uses get_unprocessed_annotations to process only new items.
    """
    scanner_name = event["name"]
    
    async with get_unprocessed_annotations("todo", scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        if not unscanned: return
        todo_data = []
        for item in unscanned.values():
            entry = item["entry"]
            key = entry.get("key", "")
            
            if key.startswith("todo"):
                app = item["parent"]
                annotation_id = entry["id"]
                annotation_value = entry["value"]
                
                app_entry = next((a for a in todo_data if a["site"] == app['site']), None)
                if not app_entry:
                    app_entry = {"site": app['site'], "url": app['url'], "annotations": [], "app": app}
                    todo_data.append(app_entry)
                
                app_entry["annotations"].append({"id": annotation_id, "key": key, "value": annotation_value})
        
        if not todo_data: return
        
        # Format as human-readable text
        ai_payload = "I have various TODOs on a bug-bounty target that I'm doing pentest on. Using the provided MCP tools, I need you to implement or investigate these TODOs. "
        ai_payload += " NOTES: 1. If application is present, assume it is in the server.\n2. Use tools as much as possible.\n3. add_annotation is for annotations only.\n4. DON'T read or write files unless necessary.\n5. Minimize requests. "
        ai_payload += "**VERY IMPORTANT** Act exclusively using the provided MCP tools: `preview_storage`, `view_storage`, `add_annotation`, `create_yaml_scheduled_function`. Do not use `read_file`, `write_file`, `replace`, or `run_shell_command`. All investigation and implementation must be performed through the application/storage interfaces or by executing logic within `run_custom_python`.\n"
        ai_payload += """**Very Important**:
  Strict Operational Constraints:
   1. No Discovery: Do not attempt to list all storages or applications to 'understand the environment.' Work
      exclusively with the specific application(s) and get_storage(s) explicitly provided in the request.
   2. No Assumptions: Do not assume tool capabilities beyond their documented descriptions. Do not guess or 'try'
      storage names (e.g., 'todos', 'functions'); only use storage names that have been confirmed for the target
      application.
   3. No Context Gathering: Skip preliminary information-gathering steps. Execute only the tool calls directly
      necessary to fulfill the specific task requested for the provided application.

  Strict Annotation Policy:
   1. No Progress Tracking: Do not use add_annotation to report that a task is started, in progress, or completed.

   2. No Task Updates: Do not annotate TODOs or tasks simply to mark them as done.

   3. Findings Only: Use add_annotation exclusively to record technical findings (e.g., discovered vulnerabilities, leaked data) or specific instructions for further scanning identified during the investigation.

   4. Provided Apps Only: currently I want you to work on the following Apps please don't try to see others unless it is requested in the TODOs or it is required to complete the TODO.

**Very Important Instructions to Follow, LEAVE THE TASK IMMEDIATELY UNTOUCHED if you will disobay any of those instructions**: 
   1. Strictly forbid the use of `create_yaml_scheduled_function`, `add_annotation`, `view_storage` (generates huge context which is unncessassery for debugging and making )for debugging, attribute introspection, or status  logging. All server-side logic must be self-contained within the requested task, and annotations must only be used to record final technical findings as defined in the 'Strict Annotation Policy.

   2. Operate with extreme data-parsimony: Use only the specific App IDs and Storage Names provided in the current request. Do not perform any exploratory tool calls to list other storages or applications. Assume all necessary context is already in the prompt; execute the required logic in the fewest calls possible, and never use tools to introspect the server environment or 'verify' the existence of resources beyond what is explicitly stated.
   3. for Bulk processing on storages, when you only need to know the structure of the storage, you can simply view a limited number of elements from the storage to see how it is defined, for example if the request requires you to operate on all .json or html files in the app-links, you can just check the response-ctype and check for json or html instead of view the whole storage as you won't operate on them the function will.
        """
        
        ai_payload += "the following are the applications with TODOs that I need you to implement now\n\n#######################\n"
        for app in todo_data:
            app_obj = app['app']
            ai_payload += f"APP ID: {app_obj['id']}\n"
            ai_payload += json.dumps(app_obj, default=str, indent=2)
            # ai_payload += "\n\nApplication TODOs:\n"
            for annotation in app['annotations']:
                annotation_content = str(annotation['value'])
                ai_payload += f" - [ID: {annotation['id']}] {annotation['key']}: {annotation_content}\n"
            ai_payload += "\n#######################\n"
            
        # Ensure it's a single line with no extra spaces
        # ai_payload = " ".join(ai_payload.split())
        ai_payload += "**Very Important** what I want you to do for EACH TODO is to first devise a plan before running any tools and reflect on that plan see if it disobays any of the provided restrictions if so rethink another plan, until the TODO is doable without disobaying any of the instructions given..."
        
        response = await mcp_server_user_interaction(ai_payload, msg_type="ai-todo")
        
        if response and response.get('finished'):
             print(f"Sent {len(todo_data)} apps with todo notes to Emacs.")
        elif response is False or response is None:
             print("No terminal available or error sending data.")


@rcn_event()
async def mcp_ai_perform_scanning(event, scheduled_md):
    """
    Scans for 'tool-scanning' notes and executes the requested tools.
    """
    
    from bs4 import BeautifulSoup as soup
    from rcn_web.scanning.utils import run_nuclei_scan, handle_nuclei_scanning_entries
    import aiofiles as aiof
    import random
    import string
    import os
    
    scanner_name = event["name"]
    
    # Process scanning annotations
    async with get_unprocessed_annotations("tool-scanning", scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        if unscanned:
            for item in unscanned.values():
                entry = item["entry"]
                xml_content = entry.get("value", "")
                
                try:
                    s = soup(xml_content, "xml")
                    
                    source_id = "nuclei-scanning"
                    if s.find("source_id"): source_id = s.find("source_id").text.strip()
                    
                    if not s.find("scanning"): continue
                    
                    base_url_text = s.find("base-url").text.strip() if s.find("base-url") else None
                    if not base_url_text: continue
                    
                    # Parse multiple URLs
                    target_urls = [u.strip() for u in base_url_text.splitlines() if u.strip()]
                    if not target_urls: continue
                    
                    templates = s.find("templates").text.strip() if s.find("templates") else ""
                    args = s.find("args").text.strip() if s.find("args") else ""
                    
                    # Create a temporary file for the targets
                    rand_str = ''.join(random.choices(string.ascii_lowercase, k=8))
                    target_file = f"/tmp/nuclei_target_{rand_str}.txt"
                    
                    async with aiof.open(target_file, "w") as f: 
                        await f.write("\n".join(target_urls))
                    
                    print(f"[AI-SCAN] Running Nuclei on {len(target_urls)} targets with templates: {templates}")
                    
                    results = await run_nuclei_scan(
                        target_file,
                        templates,
                        args,
                        timeout=event.get("timeout", ''),
                        debug=event.get("debug", False),
                        name=f"{scanner_name}-nuclei"
                    )
                    
                    # Cleanup
                    if os.path.exists(target_file): os.remove(target_file)
                    
                    # Process results
                    if results:
                        await handle_nuclei_scanning_entries(
                            [json.loads(i) for i in results.split("\n") if i.strip()],
                            source=source_id
                        )
                    
                    # Add completion annotation
                    app = item.get("parent")
                    if app:
                         global_add_annotation(None, "nuclei-scanning", f"scan-result:{source_id}", "finished", parent_id=app['id'])
                    
                except Exception as e:
                    print(f"[AI-SCAN] Error processing scanning annotation {entry.get('id')}: {e}")


@rcn_event()
async def mcp_ai_perform_fuzzing(event, scheduled_md):
    """
    Scans for 'tool-fuzzing' notes and executes the requested tools.
    """
    
    import os
    import string
    import random
    import validators
    import aiofiles as aiof
    
    from bs4 import BeautifulSoup as soup
    from rcn_web.scanning.utils import run_ffuf_scan
    
    scanner_name = event["name"]
    
    # Process fuzzing annotations
    async with get_unprocessed_annotations("tool-fuzzing", scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
         if unscanned:
             for item in unscanned.values():
                 entry = item["entry"]
                 app = item["parent"]
                 xml_content = entry.get("value", "")
                 
                 try:
                     s = soup(xml_content, "xml")
                     
                     source_id = "ai-ffuf-fuzzing"
                     if s.find("source_id"): source_id = s.find("source_id").text.strip()
                     
                     if not s.find("fuzzing"): continue
                     
                     base_dir = sys.argv[1]
                     base_url_text = s.find("base-url").text.strip() if s.find("base-url") else None
                     if not base_url_text: continue
                     
                     # Parse multiple URLs (l1)
                     target_urls = [u.strip() for u in base_url_text.splitlines() if u.strip()]
                     if not target_urls: continue
                     
                     wordlists = [] # l2, l3, ...
                     
                     # Handle l1 (URLs)
                     l1_file = None
                     if len(target_urls) > 0:
                         rand_str = ''.join(random.choices(string.ascii_lowercase, k=8))
                         l1_file = f"/tmp/fuzz_l1_{rand_str}.txt"
                         async with aiof.open(l1_file, "w") as f:
                             await f.write("\n".join(target_urls))
                         
                         # Prepend URL list as first wordlist (l1)
                         wordlists.append("file://" + l1_file)

                     for w in s.find_all("wordlist"):
                         path = w.text.strip()
                         if validators.url(path): wordlists.append(path)
                         else: wordlists.append("file://" + os.path.join(base_dir, path))
                        
                     args = s.find("args").text.strip() if s.find("args") else ""
                     dynamic_code=s.find("dynamic-code").text.strip() if s.find("dynamic-code") else None
                     
                     # Handle dynamic code generation
                     if dynamic_code:
                         try:
                             local_scope = {}
                             exec(dynamic_code, {}, local_scope)
                             if "generate_wordlist" in local_scope:
                                 generated_list = local_scope["generate_wordlist"]()
                                 if isinstance(generated_list, list):
                                     rand_str = ''.join(random.choices(string.ascii_lowercase, k=8))
                                     wl_file = f"/tmp/gen_wordlist_{rand_str}.txt"
                                     async with aiof.open(wl_file, "w") as f:
                                         await f.write("\n".join([str(i) for i in generated_list]))
                                         wordlists.append("file://" + wl_file) # TODO fix this shit
                         except Exception as e:
                             print(f"[AI-SCAN] Error executing dynamic code: {e}")
                             
                     if not wordlists:
                         print(f"[AI-SCAN] No wordlists for fuzzing {target_urls[0]}")
                         if l1_file and os.path.exists(l1_file): os.remove(l1_file)
                         continue
                     
                     print(f"[AI-SCAN] Running FFUF on {base_url} with {len(wordlists)} wordlists")
                     
                     app = item["parent"] # Application dict
                     
                     to_add = await run_ffuf_scan(
                         target_urls[0], # Primary target or placeholder
                         wordlists,
                         args,
                         timeout=event.get("timeout", ''),
                         debug=event.get("debug", False),
                         name=f"{scanner_name}-ffuf"
                     )
                     
                     # Cleanup l1
                     if l1_file and os.path.exists(l1_file): os.remove(l1_file)

                     fz_storage = get_storage_create("web-apps::fuzzing-data", parent_id=app['id'])
                     if to_add: fz_storage.add_many(to_add, source=source_id)
                     
                     # Add completion annotation
                     global_add_annotation(None, "fuzzing-data", f"scan-result:{source_id}", "finished", parent_id=app['id'])
                     
                 except Exception as e:
                     global_add_annotation(None, "fuzzing-data", f"scan-result:{source_id}", "finished", parent_id=app['id'])
                     print(f"[AI-SCAN] Error processing fuzzing annotation {entry.get('id')}: {e}")
