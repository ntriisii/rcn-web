
import re
import rcn_core.globals
from urllib.parse import urlparse

def get_scope_urls(data):
    config = rcn_core.globals.TARGET_CONFIG
    if not config.get("targets"):
        config = rcn_core.globals.YAML_FILE_CONTENT
    return get_config_urls(config)

def get_scope_wildcards(data):
    config = rcn_core.globals.TARGET_CONFIG
    if not config.get("targets"):
        config = rcn_core.globals.YAML_FILE_CONTENT
    return get_config_wildcards(config)

def get_config_wildcards(config: dict):
    wildcards = []
    
    # 1. Check if this is a target-specific config
    t_scope = config.get("scope", {})
    if isinstance(t_scope, dict) and "wildcards" in t_scope:
        wildcards.extend(t_scope.get("wildcards", []))

    # 2. Check if this is the global targets data
    else:
        targets_data = config.get("targets", {})
        if targets_data:
            for target_name, target_info in targets_data.items():
                if not isinstance(target_info, dict): continue
                t_scope = target_info.get("scope", {})
                if isinstance(t_scope, dict):
                    wildcards.extend(t_scope.get("wildcards", []))
                
    if wildcards:
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
    urls = []
    
    # 1. Check if this is a target-specific config
    t_scope = config.get("scope", {})
    if isinstance(t_scope, dict) and "urls" in t_scope:
        t_urls = t_scope.get("urls", [])
        if isinstance(t_urls, list):
            urls.extend(t_urls)
        elif isinstance(t_urls, str):
            urls.append(t_urls)

    # 2. Check if this is the global targets data
    else:
        targets_data = config.get("targets", {})
        if targets_data:
            for target_name, target_info in targets_data.items():
                if not isinstance(target_info, dict): continue
                t_scope = target_info.get("scope", {})
                if isinstance(t_scope, dict):
                    t_urls = t_scope.get("urls", [])
                    if isinstance(t_urls, list):
                        urls.extend(t_urls)
                    elif isinstance(t_urls, str):
                        urls.append(t_urls)
    if urls:
        return urls

    # Fallback to old structure

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
