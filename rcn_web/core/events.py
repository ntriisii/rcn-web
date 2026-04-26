import time
import datetime

from rcn_core.data_access import get_unprocessed_entries
from rcn_core.utils import uniq, storage_automation_md_get_create
from rcn_core.globals import RCN_FLOWS
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.scope import get_config_wildcards, get_config_urls
from rcn_web.core.utils import web_match_storage, get_target_storage, get_target_config
from rcn_core.decorators import rcn_event


@rcn_event()
async def handle_init_target(event, scheduled_md):
    event_ctx = event.copy()
    event_ctx["require-storage"] = "targets"
    event_ctx["min-entries"] = 1
    mts = get_target_storage()

    async with get_unprocessed_entries(
        "init-recon", event_ctx, target=None, match_storage_fn=web_match_storage
    ) as entries:
        target_storage = get_target_storage()
        for item in entries.values():
            entry = item["entry"]
            parent = item.get("parent")

            # Resolve ID safely
            try:
                entry_id = entry["id"]
            except (TypeError, KeyError, AttributeError):
                entry_id = getattr(entry, "id", None)

            if entry_id is None:
                continue

            # Resolve target object
            if mts.storage_md_get(f"init-recon-finished:{entry_id}"):
                continue
            if mts.storage_md_get(f"init-recon-running:{entry_id}"):
                continue

            flow_fn = RCN_FLOWS.get("init-flow")
            if not flow_fn:
                return

            flow = flow_fn()

            try:
                target_name = entry["name"]
            except (TypeError, KeyError, AttributeError):
                target_name = getattr(entry, "name", None)

            if target_name is None:
                continue

            # Use web scope helpers
            cfg = get_target_config(target_name)
            wildcards = get_config_wildcards(cfg)
            urls = get_config_urls(cfg)

            flow.set_data(wildcards)

            mts.storage_md_set(f"init-recon-running:{entry_id}", True)
            mts.storage_md_set(
                f"init-recon-started-time:{entry_id}",
                datetime.datetime.now().timestamp(),
            )

            try:
                out = await flow.run()

                out = [i.replace("..", ".").strip(".") for i in out]
                out = list(sorted(out, key=len))
                out = [i for i in urls + out]

                out = uniq(out)

                with open(
                    mts.target_directory / f"{target_name}_domains.txt", "a+"
                ) as f:
                    for d in out:
                        f.write(d + "\n")

                all_inscope = wildcards + urls
                filtered_out = []
                for domain in out:
                    if any(i in domain for i in all_inscope):
                        filtered_out.append(domain)

                out = filtered_out

                domain_st_list = get_storage_create("domains", parent_id=entry_id)
                if domain_st_list:
                    domain_st = domain_st_list[0]
                    domain_st.add_many(
                        [{"domain": i} for i in out], source="init-domains"
                    )

                mts.storage_md_set(f"init-recon-finished:{entry_id}", True)
                mts.storage_md_set(f"init-recon-running:{entry_id}", False)
            except Exception as e:
                mts.storage_md_set(f"init-recon-running:{entry_id}", False)
                raise e
