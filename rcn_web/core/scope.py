import re
import rcn_core.globals
from urllib.parse import urlparse

def get_scope_urls(data):
    config = rcn_core.globals.TARGET_CONFIG
    return get_config_urls(config)

def get_scope_wildcards(data):
    config = rcn_core.globals.TARGET_CONFIG
    return get_config_wildcards(config)

def get_config_wildcards(config: dict):
    # Support new engagement-scope structure
    if config.get("engagement-scope"):
        scope_data = config["engagement-scope"]
        wildcards = []
        if isinstance(scope_data, dict):
            # Check for 'assets' or 'targets' list
            targets = scope_data.get("assets", []) + scope_data.get("targets", [])
            for t in targets:
                if t.get("type") == "wildcard":
                    wildcards.append(t.get("value"))
                elif t.get("type") == "domain" and t.get("wildcard", False):
                    wildcards.append(t.get("value"))
        return [i.replace("*.", "").replace("*", "") for i in wildcards]

    # Fallback to old structure
    scope = config.get("scope", [])
    if not scope: return []
    wildcard_pattern = re.compile(r"\*\.?[A-Za-z-0-9]+(.[A-Za-z-0-9]+){1,}")
    
    is_multitarget = config.get("multitarget", False)
    all_wildcards = []
    if is_multitarget and isinstance(scope, dict):
        for target_name, target_scope in scope.items():
            target_wildcards = [
                i["asset_identifier"]
                for i in target_scope
                if i["asset_type"] == "WILDCARD"
                or re.match(wildcard_pattern, i["asset_identifier"])
            ]
            all_wildcards.extend(target_wildcards)
    elif isinstance(scope, list):
        all_wildcards = [
            i["asset_identifier"]
            for i in scope
            if i["asset_type"] == "WILDCARD"
            or re.match(wildcard_pattern, i["asset_identifier"])
        ]
    wild_cards = [i.replace("*.", "").replace("*", "") for i in all_wildcards]
    return wild_cards

def get_config_urls(config: dict):
    # Support new engagement-scope structure
    if config.get("engagement-scope"):
        scope_data = config["engagement-scope"]
        urls = []
        if isinstance(scope_data, dict):
            targets = scope_data.get("assets", []) + scope_data.get("targets", [])
            for t in targets:
                if t.get("type") == "url":
                    urls.append(t.get("value"))
        return urls

    scope = config.get("scope", [])
    if not scope: return []
    is_multitarget = config.get("multitarget", False)
    all_urls = []
    if is_multitarget and isinstance(scope, dict):
        for target_name, target_scope in scope.items():
            target_urls = [
                i["asset_identifier"]
                for i in target_scope
                if i["asset_type"] == "URL"
            ]
            all_urls.extend(target_urls)
    elif isinstance(scope, list):
        all_urls = [
            i["asset_identifier"]
            for i in scope
            if i["asset_type"] == "URL"
        ]
    return all_urls

def get_target_scope():
    scope = dict()
    scopewc = get_scope_wildcards([])
    scopeurl = get_scope_urls([])
    scope["wildcards"] = scopewc
    scope["urls"] = scopeurl
    return scope

def flow_in_scope(flow):
    domain = urlparse(flow["url"]).hostname
    in_scope_header = flow["request-headers"].get("x-mitmp-tab-name", "")
    scope = get_target_scope()
    if scope is None: return False
    inscope = check_domain_in_scope(domain, scope)
    return inscope or in_scope_header

def check_domain_in_scope(domain: str, scope: dict):
    if not domain: return False
    for i in scope.get("wildcards", []):
        if i in domain: return True
    for i in scope.get("urls", []):
        if domain == i: return True
    return False

def get_inscope_domains(data: list):
    scopewc = get_scope_wildcards([])
    scopeurl = get_scope_urls([])
    all_inscope = scopewc + scopeurl
    toreturn = []
    for domain in data:
        if any(i in domain for i in all_inscope):
            toreturn.append(domain)
    return toreturn
