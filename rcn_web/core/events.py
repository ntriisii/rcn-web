import time
import datetime
from rcn_core.data_access import storage, get_unprocessed_entries
from rcn_core.utils import uniq, storage_automation_md_get_create
from rcn_core.globals import RCN_FLOWS
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.scope import get_config_wildcards, get_config_urls
from rcn_web.core.utils import web_match_storage


async def handle_init_target(event, scheduled_md):
    event_ctx = event.copy()
    event_ctx["require-storage"] = "targets"
    event_ctx["max-entries"] = 1

    async with get_unprocessed_entries("init-recon", event_ctx, target=None, match_storage_fn=web_match_storage) as entries:
        for item in entries.values():
            target = item["entry"]

            if target.storage_md_get("init-recon-finished"):
                continue
            if target.storage_md_get("init-recon-running"):
                continue

            flow_fn = RCN_FLOWS.get("init-flow")
            if not flow_fn:
                continue
            
            flow = flow_fn()
            
            # Use web scope helpers
            wildcards = get_config_wildcards(target.config)
            urls = get_config_urls(target.config)
            
            flow.set_data(wildcards)

            target.storage_md_set("init-recon-running", True)
            target.storage_md_set(
                "init-recon-started-time", datetime.datetime.now().timestamp()
            )

            try:
                out = await flow.run()

                out = [i.replace("..", ".").strip(".") for i in out]
                out = list(sorted(out, key=len))
                out = [i for i in urls + out]

                out = uniq(out)

                with open(target.target_directory / "domains.txt", "a+") as f:
                    for d in out:
                        f.write(d + "\n")
                
                all_inscope = wildcards + urls

                filtered_out = []
                for domain in out:
                    if any(i in domain for i in all_inscope):
                        filtered_out.append(domain)
                out = filtered_out

                target.storage_md_set("init-recon-finished", True)
                target.storage_md_set("init-recon-running", False)

                target_md = storage_automation_md_get_create(
                    target, "check-for-new-domains"
                )

                target_md["last-check-time"] = datetime.datetime.now().timestamp()
                get_storage_create("domains", parent_id=target.id).add_many(
                    [{"domain": i} for i in out], source="init-domains"
                )

            except Exception as e:
                target.storage_md_set("init-recon-running", False)
                raise e
