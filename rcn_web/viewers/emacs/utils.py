import sys
import glob
import os
import numbers

from pentest_utils.viewers.emacs.utils import ORG_KEY_FORG
from pentest_utils.viewers.emacs.utils import make_org_tree
from pentest_utils.viewers.emacs.utils import make_preview_tabulated_entries


PAGE_LIMIT = 4000


def elisp_make_basic_tabulated_entries(dstorage, attrs=None, *args, **kwargs):
    # MAYBE: use a sample
    entries = dstorage.get()
    if not entries:
        return [], ""

    first_entry = entries[0]

    # check if the entry is dict or not if not return very basic view
    if type(first_entry) is list:
        tabulated_entries, tabulated_format = make_preview_tabulated_entries(
            tabl_entries=[{"entry": i[0]} for i in entries], attrs=(("entry", 100))
        )

    elif type(first_entry) in (str, int):
        tabulated_entries, tabulated_format = make_preview_tabulated_entries(
            tabl_entries=[{"entry": i} for i in entries],
            attrs=(("entry", 100),),
        )

    else:
        # collect keys from the first entry
        keys_to_show = []
        max_keys = 6
        for key in first_entry:
            if key in ["id", "timestamp"]:
                continue
            if len(keys_to_show) >= max_keys:
                break
            val = first_entry[key]
            if type(val) == str and len(val) < 300:
                keys_to_show.append(key)
            elif type(val) == list and len(", ".join(str(i) for i in val)) > 300:
                keys_to_show.append(key)
            elif type(val) == int:
                keys_to_show.append(key)

        # make the attrs string split the view between the entries
        padding_per_entry = len(keys_to_show) // 300

        keys_to_show.insert(0, "id")
        attrs = tuple((i, padding_per_entry) for i in keys_to_show)
        tabulated_entries, tabulated_format = make_preview_tabulated_entries(
            tabl_entries=entries, attrs=attrs, include_id=False
        )

    return tabulated_entries, tabulated_format


def elisp_make_basic_storage_view(dstorage, *args, **kwargs):
    tabulated_entries, tabulated_format = elisp_make_basic_tabulated_entries(dstorage)

    return {
        "window-config": {
            "window-1": {
                "buffer-name": "*generic-entries*",
                "mode": "tabulated-list-mode",
                "tabulated-format": tabulated_format,
                "entries": tabulated_entries,
                "navigate-fn": "rcn-view--basic-navigate-fn",
                "refresh-fn": f'(lambda () (interactive) (rcn-view--basic-refresh "{dstorage.storage_name}"))',
                "view-store": {"basic-data": {"storage-name": dstorage.storage_name}},
            },
            "window-2": {
                "buffer-name": "*generic-entries-view*",
                "mode": "org-mode",
                "entries": {},
            },
            "orientation": "horizontal",
            "scale": 0.6,
        },
    }


def elisp_make_basic_data_preview(dstorage, *args, **kwargs):
    content = dict()
    
    content["data Length"] = dstorage.length

    return content


def elisp_make_org_headline(name, entries, push_btn=None):
    headline = {
        "entries": {},
        "name": name,
    }
    if push_btn:
        headline["push-btn-fn"] = push_btn
    else:
        headline["push-btn-fn"] = "rcn-view--basic-push-btn"

    if type(entries) == dict:
        for key, value in entries.items():
            headline["entries"][key] = {"value": value, "key-foreground": ORG_KEY_FORG}

    elif type(entries) == list:
        headline["entries"][name] = [str(i) for i in entries]

    return headline


def basic_match_fn(e, value):
    return eval(value)


NOTES_CONTENT = dict()
NOTES_READ = False


def read_notes_files():
    global NOTES_CONTENT, NOTES_READ

    if NOTES_READ:
        return

    # read the files
    for file in glob.glob(os.path.join(sys.argv[1], "app-notes/*.org")):
        with open(file, "r") as f:
            NOTES_CONTENT[file.split("/")[-1]] = f.read()

    NOTES_READ = True


def get_app_notes(site):
    return NOTES_CONTENT.get(site + ".org")


def make_basic_dict_entry_view(entry):
    entry_data = dict()
    make_org_tree("Basic Entry view", entry, entry_data)

    return entry_data
