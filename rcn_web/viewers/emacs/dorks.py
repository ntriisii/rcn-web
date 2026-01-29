import sys
import rcn_core.globals

from rcn_core.utils import get_scope_wildcards

from pentest_utils.viewers.emacs.utils import make_org_link
from pentest_utils.viewers.emacs.utils import elisp_make_org_headline


def arrange_dorks_view():
    google = arrange_google_dorks_views()
    github = arrange_github_dorks_views()
    shodan = arrange_shodan_dorks_views()

    # use elisp_make_org_headline to create heading for each
    return {
        "mode": "org-mode",
        "headline": {
            "name": "Target Data",
            "key-foreground": "red",
            "entries": {
                "headlines": [
                    elisp_make_org_headline(
                        "Google Dorks", google, push_btn="rcn-view-target-google-dorks"
                    ),
                    elisp_make_org_headline(
                        "Github Dorks", github, push_btn="rcn-view-target-github-dorks"
                    ),
                    elisp_make_org_headline(
                        "Shodan Dorks",
                        shodan,
                        push_btn="rcn-view-target-shodan-dorks",
                    ),
                ]
            },
        },
        "view-store": {
            "dorks-data": {
                "default-directory": sys.argv[1],
            },
            "parent-storage": "targets",
        },
    }


def arrange_dorks_preview():

    # google = arrange_google_dorks_previews()
    # github = arrange_github_dorks_previews()
    # shodan = arrange_shodan_dorks_previews()

    gdorks = rcn_core.globals.YAML_FILE_CONTENT.get("dorks", dict()).get(
        "google-dorks", []
    )
    hdorks = rcn_core.globals.YAML_FILE_CONTENT.get("dorks", dict()).get(
        "github-dorks", []
    )
    sdorks = rcn_core.globals.YAML_FILE_CONTENT.get("dorks", dict()).get(
        "shodan-dorks", []
    )

    return {
        "google dorks length": len(gdorks),
        "github dorks length": len(hdorks),
        "shodan dorks length": len(sdorks),
    }


def interpolate_target_variables(vars, content):
    for var in vars:
        content = content.replace("{{" + var + "}}", vars[var])
    return content


def arrange_google_dorks_views():
    def include_scope_in_dorks(dork):
        scope = get_scope_wildcards([])
        dork += " AND ( "
        for i in scope:
            dork += " site:*" + i.lstrip(".") + " | "

        return dork + ")"

    intp_vars = rcn_core.globals.YAML_FILE_CONTENT.get("target-data-variables")
    dorks = rcn_core.globals.YAML_FILE_CONTENT.get("dorks", dict()).get(
        "google-dorks"
    )
    if not dorks:
        return dict()

    collected_dorks = []
    # collect the
    for dork in dorks:
        val = dorks[dork]
        val = interpolate_target_variables(intp_vars, val)
        val = include_scope_in_dorks(val)

        # include the site from th scope
        collected_dorks.append(
            make_org_link(f"https://www.google.com/search?q={val}", dork)
        )

    return collected_dorks


def arrange_github_dorks_views():
    intp_vars = rcn_core.globals.YAML_FILE_CONTENT.get("target-data-variables")
    dorks = rcn_core.globals.YAML_FILE_CONTENT.get("dorks", dict()).get(
        "github-dorks"
    )
    if not dorks:
        return dict()

    collected_dorks = []
    # collect the
    for dork in dorks:
        val = dorks[dork]
        val = interpolate_target_variables(intp_vars, val)

        # include the site from th scope
        collected_dorks.append(
            make_org_link(f"https://github.com/search?q={val}", dork)
        )

        collected_dorks[dork] = val

    return collected_dorks


def arrange_shodan_dorks_views():
    intp_vars = rcn_core.globals.YAML_FILE_CONTENT.get("target-data-variables")
    dorks = rcn_core.globals.YAML_FILE_CONTENT.get("dorks", dict()).get(
        "shodan-dorks"
    )
    if not dorks:
        return dict()

    collected_dorks = []
    # collect the
    for dork in dorks:
        val = dorks[dork]
        val = interpolate_target_variables(intp_vars, val)

        # include the site from th scope
        collected_dorks.append(
            make_org_link(f"https://www.shodan.io/search?query={val}", dork)
        )

    return collected_dorks


def arrange_google_dorks_previews():
    pass


def arrange_github_dorks_previews():
    pass


def arrange_shodan_dorks_previews():
    pass
