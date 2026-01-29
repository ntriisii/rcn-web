import typing
import subprocess
import aiofiles as aiof

from operator import itemgetter
from itertools import groupby
from contextlib import asynccontextmanager
from functools import partial

from rcn_web.core.utils import storage
from rcn_web.core.utils import parse_json, web_match_storage
from rcn_core.storage.bases import get_storage_create, add_annotation as global_add_annotation
from pentest_utils.ai import ai_ask
from .utils import get_unprocessed_entries



async def ai_annotate_link_entries(event, scheduled_md):
    
    def _annotate_link(link_id, annotation, tag, link_id_mappings):
        if link_id not in link_id_mappings: return
        link_obj = link_id_mappings[link_id]
        lid, storage, parent_id = link_obj
        
        global_add_annotation(entry_id=lid['id'], storage_name=storage.storage_name, key=tag, value=annotation, parent_id=parent_id)
    
    def _add_annotations(link_id, note, link_id_mappings):
        if link_id not in link_id_mappings: return 
        link_obj = link_id_mappings[link_id]
        lid, storage, parent_id = link_obj
        
        global_add_annotation(entry_id=lid['id'], storage_name=storage.storage_name, key="ai-notes", value=note, parent_id=parent_id)
    
    scanner_name = event["name"]
    base_prompt = event["ai-base-prompt"]
    user_ai_prompt = event["ai-collect-instructions"]
    user_ai_tags = event["ai-tags"]
    model = event.get("model", "gemini-flash-latest")
    apps_prompt_data = ""
    
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        # add an extra ID index for the AI to recognize the URL
        for i, link in enumerate(unscanned, 1): unscanned[link]["ai-index"] = i
        
        # return 
        # group the items by app: [links]
        # so the structure looks like this {<app>: [{"link": {...}, "app": <app>}, ... ]}
        # app_links_mapping = dict(groupby(unscanned.values(), lambda x: x['parent']))
        # app_links_mapping = {i:list(j) for i,j in app_links_mapping.items()}
        link_indx_mapping = {}
        app_links_mapping = {}
        for i in unscanned.values():
            app = i["parent"]
            if app in app_links_mapping: app_links_mapping[app].append(i)
            else: app_links_mapping[app] = [i]
        
        ### create the app links data for the AI
        # create the app data for the AI
        for app in app_links_mapping:
            links = list((i["entry"], i["ai-index"]) for i in app_links_mapping[app])
            # TODO: include notes from the user and more info about fuzzing and scanning
            app_ai_data = f"""
{app.get('scheme')}://{app.get('site')}/
{app.get('technologies')}
{app.get('title')}
{app.get('status_code')}
{len(get_storage_create('web-apps::app-links', parent_id=app['id']))}
---
{'\n'.join(str(i[1]) + '  ' + i[0]['method'] + '  ' + i[0]['path'] + '  **  ' +i[0].get('data', '') for i in links)}
      """

            apps_prompt_data += app_ai_data + "\n#####"

        link_indx_mapping = {
            unscanned[link]["ai-index"]: (
                unscanned[link]["entry"],
                unscanned[link]["storage"],
                unscanned[link]["parent"]["id"]
            )
            for link in unscanned
        }
        # print("#######################")
        # print("#######################")
        # print(
        #     base_prompt.format(
        #         apps_prompt=apps_prompt_data,
        #         ai_interesting_urls_prompt=user_ai_prompt,
        #         ai_tags=user_ai_tags,
        #     )
        # )

        print("Prompt data length: ", len(apps_prompt_data) / 4)

        # return 
        # ask AI and parse the outfunction
        if apps_prompt_data:
            trails = 0
            while trails < 5:
                # try:
                    # ai_response = await ai_ask(
                    #     base_prompt.format(
                    #         apps_prompt=apps_prompt_data,
                    #         ai_interesting_urls_prompt=user_ai_prompt,
                    #         ai_tags=user_ai_tags,
                    #     ),
                    #     model=model,
                    # )
                    # ai_response = (ai_response.strip().removeprefix("```python").removesuffix("```"))
                ai_response = """
def ai_annotate_links():
    # Application: http://vpn2.api.mail1.t5.epam.lvh.me:80/
    annotate_link(2, "D:page,lang", "potential-xss")
    annotate_link(1545, "D:eval", "potential-rce")
    annotate_link(1546, "D:id", "potential-sqli")
    annotate_link(1546, "D:path", "potential-path-traversal")
    annotate_link(1548, "D:script,q", "potential-xss")
    annotate_link(1548, "D:filepath", "potential-path-traversal")
    annotate_link(1550, "D:xml", "potential-xxe")
    annotate_link(1550, "D:filename", "potential-file-upload")
    annotate_link(1551, "D:cmd,code", "potential-rce")
    annotate_link(1551, "D:key", "potential-sqli")
    add_notes(1551, "Missing CSRF token on POST request accepting RCE-prone parameters.")
    annotate_link(1553, "D:path", "potential-path-traversal")
    annotate_link(1553, "D:table", "potential-sqli")
    annotate_link(1554, "D:statement", "potential-sqli")
    annotate_link(1554, "D:json", "potentail-ssrf")
    annotate_link(1566, "D:xml", "potential-xxe")
    annotate_link(1566, "D:link", "potentail-ssrf")
    add_notes(1566, "Missing CSRF token on POST request.")
    for idx in [1568, 1601, 1606]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")
        add_notes(idx, "Authentication endpoint found.")
    annotate_link(1598, "D:user_search", "potential-sqli")
    annotate_link(1607, "D:table", "potential-sqli")
    annotate_link(1607, "D:template", "potential-xss")
    annotate_link(1626, "D:eval", "potential-rce")
    annotate_link(1626, "D:url", "potentail-ssrf")
    annotate_link(1626, "D:redirect", "potential-xss")
    annotate_link(1630, "D:limit,column", "potential-sqli")
    annotate_link(1631, "D:script", "potential-xss")
    annotate_link(1631, "D:filepath", "potential-path-traversal")
    annotate_link(1632, "D:limit", "potential-sqli")

    # Application: http://db.ht7.gf.h57z.epam.lvh.me:80/
    for idx, note in {6: "jobs admin panel", 7: "jobs admin dev users v2 listing", 9: "team admin panel", 14: "hiring admin api access"}.items():
        add_notes(idx, f"Check for unauthorized access to {note}.")
    annotate_link(12, "D:key,search", "potential-sqli")
    annotate_link(13, "D:column", "potential-sqli")
    annotate_link(15, "D:filepath", "potential-path-traversal")
    annotate_link(15, "D:exec", "potential-rce")
    annotate_link(18, "D:json", "potentail-ssrf")
    add_notes(18, "Missing CSRF token.")
    annotate_link(20, "D:sql", "potential-sqli")
    annotate_link(20, "D:json", "potentail-ssrf")
    for idx in [21, 72, 145, 148]:
        annotate_link(idx, "D:user_search", "potential-sqli")
    annotate_link(56, "Q:pid", "potential-idor")
    for idx in [16, 19, 69, 139]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")
        add_notes(idx, "Authentication endpoint found.")
    for idx in [26, 142, 147]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")
        add_notes(idx, "Authentication endpoint for Admin/Privileged resource.")
    annotate_link(70, "D:statement", "potential-sqli")
    annotate_link(70, "D:uri", "potentail-ssrf")
    annotate_link(74, "D:sort", "potential-sqli")
    annotate_link(76, "D:offset", "potential-sqli")
    add_notes(76, "Admin POST endpoint for posts.")
    annotate_link(77, "D:filter", "potential-sqli")
    annotate_link(77, "D:script", "potential-xss")
    annotate_link(78, "D:filepath", "potential-path-traversal")
    annotate_link(78, "D:link", "potentail-ssrf")
    annotate_link(132, "D:statement", "potential-sqli")
    annotate_link(132, "D:link", "potentail-ssrf")
    annotate_link(137, "D:sql", "potential-sqli")
    annotate_link(138, "D:exec", "potential-rce")
    annotate_link(140, "D:template", "potential-path-traversal")
    annotate_link(140, "D:url", "potentail-ssrf")
    annotate_link(141, "D:path", "potential-path-traversal")
    annotate_link(141, "D:redirect", "potential-xss")
    for idx in [164, 170]:
        annotate_link(idx, "Q:price_min", "potential-sqli")

    # Application: http://j6.app3.6z.monitor.secure.epam.lvh.me:80/
    annotate_link(184, "D:query", "potential-sqli")
    annotate_link(185, "D:user_search", "potential-sqli")
    annotate_link(186, "D:sql", "potential-sqli")
    add_notes(186, "SQL injection point in admin path.")
    annotate_link(187, "D:sql", "potential-sqli")
    add_notes(187, "SQL injection point in admin path.")
    annotate_link(188, "D:filename", "potential-path-traversal")
    add_notes(188, "Missing CSRF token.")
    annotate_link(193, "D:column,table,q", "potential-sqli")
    annotate_link(196, "D:script", "potential-xss")
    annotate_link(196, "D:filename", "potential-file-upload")
    annotate_link(210, "D:page", "potential-path-traversal")
    add_notes(210, "Missing CSRF token.")
    annotate_link(252, "D:cmd", "potential-rce")
    for idx in [269, 319, 335, 340]:
        annotate_link(idx, "D:user_search", "potential-sqli")
    annotate_link(273, "D:statement", "potential-sqli")
    annotate_link(275, "D:eval", "potential-rce")
    annotate_link(279, "D:file", "potential-file-upload")
    annotate_link(279, "D:template", "potential-path-traversal")
    add_notes(279, "Admin endpoint handling file and template names.")
    annotate_link(281, "D:statement", "potential-sqli")
    annotate_link(344, "D:cmd,code", "potential-rce")
    add_notes(344, "Missing CSRF token on POST request accepting RCE-prone parameters.")
    for idx in [194, 206, 278]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")
    for idx in [274, 336]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")
        add_notes(idx, "Authentication endpoint in admin path.")

    # Application: http://jenkins.oh.in.i2a.epam.lvh.me:80/
    for idx in [356, 357]:
        add_notes(idx, "Check IDOR/access control for private resource.")
    annotate_link(361, "D:template", "potential-path-traversal")
    annotate_link(365, "D:statement", "potential-sqli")
    annotate_link(366, "D:cmd", "potential-rce")
    annotate_link(366, "D:statement", "potential-sqli")
    annotate_link(370, "D:statement,query", "potential-sqli")
    annotate_link(374, "D:limit,query", "potential-sqli")
    annotate_link(375, "D:eval", "potential-rce")
    add_notes(375, "Missing CSRF token on RCE-prone endpoint.")
    annotate_link(376, "D:uri", "potentail-ssrf")
    annotate_link(376, "D:file", "potential-file-upload")
    for idx in [433, 436, 444]:
        annotate_link(idx, "D:user_search", "potential-sqli")
    annotate_link(435, "D:path", "potential-path-traversal")
    annotate_link(437, "D:file", "potential-file-upload")
    add_notes(437, "Missing CSRF token.")
    annotate_link(439, "D:id,statement", "potential-sqli")
    annotate_link(439, "D:filename", "potential-path-traversal")
    annotate_link(508, "D:redirect", "potential-xss")
    annotate_link(509, "D:search", "potential-sqli")
    add_notes(509, "Missing CSRF token.")
    annotate_link(510, "D:eval", "potential-rce")
    annotate_link(510, "D:filename", "potential-path-traversal")
    annotate_link(513, "D:uri", "potentail-ssrf")
    annotate_link(517, "D:command", "potential-rce")
    annotate_link(517, "D:xml", "potential-xxe")
    annotate_link(519, "D:limit,filter", "potential-sqli")
    for idx in [368, 372, 378, 516]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")

    # Application: http://jira.r8b.web.epam.lvh.me:80/
    annotate_link(538, "D:template", "potential-path-traversal")
    annotate_link(539, "D:code", "potential-rce")
    for idx in [542, 551]:
        annotate_link(idx, "D:user_search", "potential-sqli")
    annotate_link(543, "D:command", "potential-rce")
    annotate_link(543, "D:query", "potential-sqli")
    annotate_link(545, "D:filepath", "potential-path-traversal")
    annotate_link(546, "D:key", "potential-sqli")
    annotate_link(549, "D:filepath,file", "potential-path-traversal")
    annotate_link(549, "D:file", "potential-file-upload")
    annotate_link(569, "D:file", "potential-file-upload")
    add_notes(569, "Missing CSRF token.")
    annotate_link(588, "D:eval", "potential-rce")
    annotate_link(588, "D:xml", "potential-xxe")
    annotate_link(588, "D:link", "potentail-ssrf")
    add_notes(588, "Missing CSRF token on critical RCE/XXE endpoint.")
    annotate_link(591, "D:limit", "potential-sqli")
    annotate_link(593, "D:exec", "potential-rce")
    annotate_link(593, "D:xml", "potential-xxe")
    annotate_link(593, "D:filename", "potential-path-traversal")
    add_notes(593, "Missing CSRF token on critical RCE/XXE endpoint.")
    annotate_link(639, "D:file", "potential-file-upload")
    annotate_link(639, "D:file", "potential-path-traversal")
    annotate_link(641, "D:query", "potential-sqli")
    annotate_link(642, "D:uri", "potentail-ssrf")
    annotate_link(643, "D:sql", "potential-sqli")
    annotate_link(646, "D:exec", "potential-rce")
    annotate_link(646, "D:sort", "potential-sqli")
    annotate_link(693, "D:url", "potentail-ssrf")
    annotate_link(694, "D:column,key", "potential-sqli")
    annotate_link(694, "D:url", "potentail-ssrf")
    for idx in [595, 645]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")

    # Application: http://ns.sso.d0ea.epam.lvh.me:80/
    annotate_link(529, "Q:price_min", "potential-sqli")
    annotate_link(1359, "D:offset", "potential-sqli")
    add_notes(1359, "Missing CSRF token.")
    annotate_link(1361, "D:path", "potential-path-traversal")
    annotate_link(1363, "D:code,cmd", "potential-rce")
    annotate_link(1363, "D:xml", "potential-xxe")
    add_notes(1363, "Critical RCE/XXE endpoint.")
    annotate_link(1364, "D:eval", "potential-rce")
    annotate_link(1365, "D:xml", "potential-xxe")
    add_notes(1365, "Missing CSRF token.")
    annotate_link(1366, "D:eval,exec", "potential-rce")
    annotate_link(1369, "D:command", "potential-rce")
    annotate_link(1369, "D:offset", "potential-sqli")
    annotate_link(1380, "D:command", "potential-rce")
    annotate_link(1380, "D:filename", "potential-path-traversal")
    annotate_link(1445, "D:q", "potential-sqli")
    annotate_link(1498, "D:sql", "potential-sqli")
    annotate_link(1498, "D:uri", "potentail-ssrf")
    annotate_link(1501, "D:filter,column", "potential-sqli")
    annotate_link(1504, "D:eval", "potential-rce")
    annotate_link(1504, "D:filename,filepath", "potential-path-traversal")
    annotate_link(1511, "D:url", "potentail-ssrf")
    annotate_link(1511, "D:id", "potential-sqli")
    add_notes(1511, "Missing CSRF token on private resource.")
    add_notes(1512, "Private registration endpoint.")
    for idx in [1360, 1446, 1456, 1513]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")
    for idx in [1373, 1458, 1499, 1508]:
        annotate_link(idx, "D:user_search", "potential-sqli")

    # Application: http://prod6.jenkins.git.mcmo.epam.lvh.me:80/
    for idx in [707, 721, 722, 804, 812]:
        annotate_link(idx, "D:user_search", "potential-sqli")
    add_notes(722, "Check restore functionality for IDOR or privilege escalation.")
    annotate_link(719, "D:path", "potential-path-traversal")
    annotate_link(719, "D:offset,filter", "potential-sqli")
    annotate_link(720, "D:path", "potential-path-traversal")
    annotate_link(720, "D:uri", "potentail-ssrf")
    annotate_link(720, "D:redirect", "potential-xss")
    annotate_link(723, "D:url", "potentail-ssrf")
    annotate_link(723, "D:xml", "potential-xxe")
    annotate_link(724, "D:xml", "potential-xxe")
    annotate_link(724, "D:filepath", "potential-path-traversal")
    annotate_link(726, "D:filter,limit", "potential-sqli")
    annotate_link(726, "D:script", "potential-xss")
    annotate_link(756, "D:redirect", "potential-xss")
    add_notes(756, "Missing CSRF token.")
    annotate_link(807, "D:key", "potential-sqli")
    for idx in [802, 808]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")

    # Application: http://portal.shop.ns.epam.lvh.me:80/
    annotate_link(859, "D:xml", "potential-xxe")
    annotate_link(859, "D:table", "potential-sqli")
    annotate_link(862, "D:id", "potential-sqli")
    annotate_link(864, "D:script", "potential-xss")
    annotate_link(865, "D:exec,eval", "potential-rce")
    add_notes(865, "RCE via exec/eval parameters in admin path.")
    annotate_link(866, "D:xml", "potential-xxe")
    annotate_link(866, "D:template", "potential-path-traversal")
    annotate_link(910, "D:exec", "potential-rce")
    annotate_link(910, "D:limit", "potential-sqli")
    annotate_link(914, "D:column", "potential-sqli")
    annotate_link(915, "D:link", "potentail-ssrf")
    add_notes(915, "Missing CSRF token.")
    for idx in [960, 962]:
        annotate_link(idx, "D:column,limit", "potential-sqli")
    annotate_link(966, "D:user_search", "potential-sqli")
    annotate_link(968, "D:limit", "potential-sqli")
    annotate_link(968, "D:path", "potential-path-traversal")
    annotate_link(969, "D:q", "potential-xss")
    annotate_link(969, "D:redirect", "potential-xss")
    annotate_link(971, "D:xml", "potential-xxe")
    for idx in [875, 881, 906, 909, 974]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")

    # Application: http://monitor3.dr.z0kf.bm1.epam.lvh.me:80/
    annotate_link(1012, "P:2-4", "potential-path-traversal")
    for idx in [1014, 1015]:
        add_notes(idx, "Check IDOR/Auth on access level defined in path.")
    annotate_link(1020, "D:uri", "potentail-ssrf")
    annotate_link(1020, "D:filename", "potential-path-traversal")
    annotate_link(1021, "D:user", "potential-sqli")
    annotate_link(1023, "D:xml", "potential-xxe")
    annotate_link(1023, "D:script", "potential-xss")
    annotate_link(1024, "D:filter", "potential-sqli")
    annotate_link(1028, "D:limit", "potential-sqli")
    annotate_link(1029, "D:user_search", "potential-sqli")
    annotate_link(1039, "D:key", "potential-sqli")
    annotate_link(1113, "D:exec", "potential-rce")
    annotate_link(1113, "D:uri", "potentail-ssrf")
    annotate_link(1113, "D:file", "potential-file-upload")
    annotate_link(1114, "P:4", "potential-path-traversal")
    annotate_link(1115, "D:cmd", "potential-rce")
    annotate_link(1115, "D:sort", "potential-sqli")
    annotate_link(1168, "D:sql", "potential-sqli")
    annotate_link(1168, "D:filepath", "potential-path-traversal")
    add_notes(1168, "Missing CSRF token on SQL/LFI prone endpoint.")
    annotate_link(1174, "D:link,uri", "potentail-ssrf")
    annotate_link(1174, "D:column", "potential-sqli")
    annotate_link(1175, "D:url", "potentail-ssrf")
    annotate_link(1176, "D:json,xml", "potential-xxe")
    add_notes(1176, "Missing CSRF token.")
    for idx in [1026, 1033]:
        annotate_link(idx, "D:login_user,login_pass", "potential-sqli")
    add_notes(1026, "Auth endpoint for privileged path (executive).")

    # Application: http://nhus.prod6.2sh.epam.lvh.me:80/
    annotate_link(1187, "D:filename", "potential-path-traversal")
    annotate_link(1187, "D:column", "potential-sqli")
    annotate_link(1188, "D:offset", "potential-sqli")
    annotate_link(1189, "D:json", "potentail-ssrf")
    add_notes(1189, "Missing CSRF token.")
    annotate_link(1190, "D:cmd", "potential-rce")
    annotate_link(1190, "D:query", "potential-sqli")
    annotate_link(1194, "D:filepath", "potential-path-traversal")
    annotate_link(1195, "D:sort", "potential-sqli")
    annotate_link(1202, "D:id", "potential-sqli")
    annotate_link(1205, "D:exec", "potential-rce")
    annotate_link(1205, "D:script", "potential-xss")
    annotate_link(1259, "D:q", "potential-sqli")
    add_notes(1259, "Missing CSRF token.")
    annotate_link(1269, "D:command", "potential-rce")
    annotate_link(1270, "D:eval", "potential-rce")
    annotate_link(1270, "D:path", "potential-path-traversal")
    annotate_link(1271, "D:code", "potential-rce")
    annotate_link(1275, "D:uri", "potentail-ssrf")
    annotate_link(1341, "D:sql", "potential-sqli")
    pass


                          """

                annotate_link = partial(_annotate_link, link_id_mappings=link_indx_mapping)
                add_notes = partial(_add_annotations, link_id_mappings=link_indx_mapping)
                exec_scope = {"annotate_link": annotate_link, "add_notes": add_notes}
                # print("******************")
                # print("The response from the AI function is: ")
                # print(ai_response)
                # print("******************")
                exec(ai_response, exec_scope)

                ai_fn = exec_scope["ai_annotate_links"]

                ai_fn()
                break
                
                # except Exception as e:
                #     trails += 1
                #     print(f"Error in ai_annotate_link_entries: {e}. Retrying...")

        # print("#######################")
        # print("#######################")
