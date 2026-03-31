import os
import sys
import glob
import pathlib
import asyncio
import aiofiles as aiof
import aiohttp


from rcn_core.decorators import rcn_event

@rcn_event()
async def request_gau_entries(event, md=None):
    target = event.get("target")
    if target:
        target_dir = target.target_directory
    else:
        target_dir = pathlib.Path(sys.argv[1])

    gau_urls_path = target_dir / ".gau_urls/"

    if not gau_urls_path.exists():
        return

    files = glob.glob(gau_urls_path.as_posix() + "*")
    max_request_per_time = event.get("max-requests-per-time", 2000)
    concurrent_requests = event.get("concurrent-requests", 5)

    # keep reading files until you reached the number of requests specified
    files_counter = 0
    urls = []
    while len(urls) < max_request_per_time and files_counter < len(files):
        async with aiof.open(files[files_counter], "r") as f:
            content = (await f.read()).split("\n")
            # Logic correction: to collect UP TO max_request.
            # currently logic is weird in old code: req = content[max - len:] ??
            # Usually you take from the START: content[:needed]

            needed = max_request_per_time - len(urls)
            to_take = content[:needed]
            rest = content[needed:]

            urls.extend(to_take)

        if rest:
            # Rewrite file with remaining
            async with aiof.open(files[files_counter], "w") as f:
                await f.write("\n".join(rest))
            # We found enough urls in this file (since rest exists or we took exact amount)
            # but wait, if rest exists, we stop here? loop condition handles len(urls)
            pass
        else:
            # File fully consumed
            files_counter += 1

    # Execution logic
    # Note: Proxy hardcoded to localhost:8081
    async with aiohttp.ClientSession() as ses:
        tasks = []
        for u in urls:
            if not u:
                continue
            tasks.append(
                asyncio.create_task(ses.head(u, proxy="http://localhost:8081"))
            )

            if len(tasks) >= concurrent_requests:
                await asyncio.gather(*tasks)
                tasks = []

        if tasks:
            await asyncio.gather(*tasks)

    # delete those files that you have requested fully
    # files_counter points to the first file that HAS NOT been fully consumed or index out of bounds
    to_delete_files = files[:files_counter]
    for f in to_delete_files:
        try:
            os.remove(f)
        except OSError:
            pass
