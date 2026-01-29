from .utils import *


def proxy_history_views_make_tabulated_entries(
    views: list,
    match_groups,
    match_fn,
    page=0,
    limit=PAGE_LIMIT,
):

    attrs = (
        ("index", 0),
        ("path", 75),
        ("status", 4),
        ("method", 5),
        ("response-ctype", 7),
        ("data", 5),
        ("tags", 10),
        ("found-vulns", 3),
        ("vuln-checked", 2),
        ("timestamp", 3),
        ("inline-js", 10),
        ("title", 10),
    )


def proxy_history_view(
    cache_views: list, page=0, reset_page_counter=False, match_groups=dict()
):

    global PAGE_ID_MAPPING
