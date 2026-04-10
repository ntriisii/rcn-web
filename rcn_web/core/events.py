import time
import datetime

from rcn_core.data_access import get_unprocessed_entries
from rcn_core.utils import uniq, storage_automation_md_get_create
from rcn_core.globals import RCN_FLOWS
from rcn_core.storage.bases import get_storage_create
from rcn_web.core.scope import get_config_wildcards, get_config_urls
from rcn_web.core.utils import web_match_storage, get_root_storage
from rcn_core.decorators import rcn_event


def _resolve_target(item):
    """Resolve a dict entry from the targets table to a TargetStorage object.

    If the entry is already a rich object (e.g. from tests), return it as-is.
    If it is a plain dict, look up the parent and resolve via
    parent.get_target_storage(name).
    """
    from rcn_core.log import rlog
    target = item["entry"]
    rlog(f"_resolve_target: entry type={type(target).__name__}, entry={target}", level="info")

    # Already a rich object (e.g. MockTargetEntry in tests)
    if hasattr(target, "storage_md_get") and hasattr(target, "config"):
        rlog("_resolve_target: entry is already a rich object", level="info")
        return target

    # Plain dict — need to resolve via parent
    parent = item.get("parent")
    rlog(f"_resolve_target: parent={parent}, type={type(parent).__name__ if parent else None}", level="info")
    if parent is None:
        rlog("_resolve_target: no parent, returning None", level="info")
        return None

    target_name = target.get("name")
    if not target_name:
        rlog(f"_resolve_target: no 'name' in entry, returning None", level="info")
        return None

    # parent may be MultiTargetStorage or another container with
    # get_target_storage(name)
    if hasattr(parent, "get_target_storage"):
        rlog(f"_resolve_target: resolving via parent.get_target_storage('{target_name}')", level="info")
        result = parent.get_target_storage(target_name)
        rlog(f"_resolve_target: result={result}, type={type(result).__name__ if result else None}", level="info")
        return result

    # Try get_root_storage as fallback
    root = get_root_storage()
    rlog(f"_resolve_target: fallback root={root}, type={type(root).__name__ if root else None}", level="info")
    if root and hasattr(root, "get_target_storage"):
        result = root.get_target_storage(target_name)
        rlog(f"_resolve_target: fallback result={result}", level="info")
        return result

    rlog("_resolve_target: could not resolve, returning None", level="info")
    return None


@rcn_event()
async def handle_init_target(event, scheduled_md):
    event_ctx = event.copy()
    event_ctx["require-storage"] = "targets"
    event_ctx["max-entries"] = 1
    async with get_unprocessed_entries("init-recon", event_ctx, target=None, match_storage_fn=web_match_storage) as entries:
        from rcn_core.log import rlog
        rlog(f"init-recon: got {len(entries)} unprocessed entries", level="info")
        for key, item in entries.items():
            rlog(f"init-recon: item key={key}, entry type={type(item['entry']).__name__}, entry={item.get('entry')}", level="info")
            target = _resolve_target(item)
            rlog(f"init-recon: resolved target={target}, type={type(target).__name__ if target else None}", level="info")
            if target is None:
                continue

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
