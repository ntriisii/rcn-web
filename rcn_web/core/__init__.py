import os
import sys
import rich
import traceback

from .utils import *

# from .init_target import *
# from .data_storage import *
# from .scanning import *

# from .proxy import *
# from .viewers import *
from .events import *
from .test_events import *
from .remote_flow_processor import *
# from .flows import *

from rcn_core.utils import *


def run_yml_func(
    fn,
    *args,
    **kwargs,
):
    try:
        return fn(*args, **kwargs)
    except BaseException as err:
        rlog(f"there was an error while running {fn.__name__} -> {err}", level="error")

        con = rich.console.Console()
        con.print_exception(show_locals=False)


def yaml_make_proper_fn_name(node, evaluate=True):
    fn = ""
    if node.startswith("py_"):
        fn = node[3:]
    else:
        # check if the function is a python function or a lambda expression
        if "\n" in node:
            node = node.strip()
            if evaluate:
                exec(node)

                fn_name = re.findall("def (.*?)\(", node)
                if fn_name:
                    fn_name = fn_name[0]
                    return eval(fn_name) if evaluate else fn_name

                return exec(node)

            else:
                return node

        else:
            fn = re.sub(r"\((.*)\) *-> *", r"lambda \1: ", node)

    fn = f"{fn}"
    if evaluate:
        return eval(fn)
    return fn


def add_dict(dc, key, val):
    dc[key] = val
    return dc


def update_dict(dc, new):

    for i in new:
        if i not in dc.keys():
            dc[i] = new[i]
        else:
            dc[i].update(new[i])

    return dc


def delete_entries_list(entries, ev):
    to_del = []

    for i, e in enumerate(entries):
        if eval(ev):
            to_del.append(i)

    count = 0
    for i in to_del:
        del entries[i - count]
        count += 1


def delete_entries_dict(entries, ev):
    to_del = []
    for k in entries:
        e = entries[k]
        if eval(ev):
            to_del.append(k)

    for i in to_del:
        del entries[i]


def store_domains_in_file(domains):
    with open(os.path.join(sys.argv[1], "domains.txt"), "a+") as f:
        for d in domains:
            f.write(d + "\n")


def get_proxy_data():

    proxy_config = rcn_core.globals.YAML_FILE_CONTENT

    # preprocess the content file
    data = dict()
    import_files = list(proxy_config.get("import-files", []))
    import_files.extend(proxy_config.get("repeater-import-files", []))
    data["import-files"] = import_files
    data["extractors"] = proxy_config.get("extractors", dict())
    data["match-and-replace"] = proxy_config.get("match-and-replace", dict())
    data["match-and-drop"] = proxy_config.get("match-and-drop", [])
    data["content-filter"] = proxy_config.get("content-filter", [])

    return data


RE_UPDATE_PROXY = True


async def proxy_snyc(event):

    global RE_UPDATE_PROXY

    try:
        async with aiohttp.ClientSession() as sess:
            resp = await sess.get("http://localhost:8081/")

    except aiohttp.ClientConnectionError:
        RE_UPDATE_PROXY = True
        return

    if RE_UPDATE_PROXY:
        async with aiohttp.ClientSession() as sess:
            data = get_proxy_data()
            await sess.post(url="http://localhost:8082/updateRcn-ServerData", json=data)

        RE_UPDATE_PROXY = False
