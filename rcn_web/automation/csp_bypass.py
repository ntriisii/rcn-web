
import re
from urllib.parse import urlparse
from collections import defaultdict
from rcn_core.log import rlog
from rcn_core.data_access import storage
from rcn_core.data_access import get_unprocessed_entries
from rcn_web.core.utils import get_app_by_site, web_match_storage
from rcn_core.utils import flow_in_scope
from rcn_core.storage.bases import add_annotation as global_add_annotation

# --- Constants ---

BASE_URI = "base-uri"
FORM_ACTION = "form-action"
FRAME_ANCESTORS = "frame-ancestors"
PLUGIN_TYPES = "plugin-types"
REPORT_URI = "report-uri"
SANDBOX = "sandbox"
UPGRADE_INSECURE_REQUESTS = "upgrade-insecure-requests"
REFLECTIVE_XSS = "reflected-xss"
REFERRER = "referrer"

DEFAULT_SRC = "default-src"
SCRIPT_SRC = "script-src"
CHILD_SRC = "child-src"
FRAME_SRC = "frame-src"
CONNECT_SRC = "connect-src"
FONT_SRC = "font-src"
IMG_SRC = "img-src"
MEDIA_SRC = "media-src"
OBJECT_SRC = "object-src"
STYLE_SRC = "style-src"
MANIFEST_SRC = "manifest-src"

SELF = "'self'"
NONE = "'none'"
UNSAFE_INLINE = "'unsafe-inline'"
UNSAFE_EVAL = "'unsafe-eval'"
HTTP = "http:"
HTTPS = "https:"
BLOB = "blob:"
DATA = "data:"
FILESYSTEM = "filesystem:"
MEDIASTREAM = "mediastream:"

# --- CSP Known Bypasses ---

CSP_KNOWN_BYPASSES = {
    "script-src": [
        # (DOMAIN, DESCRIPTION/EXAMPLE,)
        ("ajax.googleapis.com", '''
Additional information is available here:  https://github.com/cure53/XSSChallengeWiki/wiki/H5SC-Minichallenge-3:-%22Sh*t,-it%27s-CSP!%22

Example Payload:
"><script src=//ajax.googleapis.com/ajax/services/feed/find?v=1.0%26callback=alert%26context=1337></script>
'''),
    ]
}

# --- Helpers ---

def csp_match_domains(content_src, domain):
    """ Does a `content_src' allow a `domain' """
    # Isolate just the domain incase there is a scheme/etc.
    content_src = content_src.lower()
    domain = domain.lower()
    
    parsed = urlparse(content_src)
    if parsed.netloc != '':
        content_src = parsed.netloc

    src_parts = content_src.split(".")[::-1]  # Reverse the domains
    domain_parts = domain.split(".")[::-1]
    for index, src_part in enumerate(src_parts):
        if src_part == "*":
            return True
        if index >= len(domain_parts):
            return False
        if src_part == domain_parts[index]:
            continue
        else:
            return False
    return len(src_parts) == len(domain_parts)

class ContentSecurityPolicy(object):

    """
    A simple Content-Security-Policy object, it resembles a dictionary but has
    logic to return `default-src' when approiate, etc.
    """

    HEADERS = ["content-security-policy",
               "content-security-policy-report-only",
               "x-content-security-policy",
               "x-webkit-csp"]

    # All content directives
    CONTENT_DIRECTIVES = [
        DEFAULT_SRC, SCRIPT_SRC, CHILD_SRC, FRAME_SRC, CONNECT_SRC, FONT_SRC,
        IMG_SRC, MEDIA_SRC, OBJECT_SRC, STYLE_SRC, MANIFEST_SRC,

        BASE_URI, FORM_ACTION, FRAME_ANCESTORS, PLUGIN_TYPES,
        REPORT_URI, SANDBOX, REFLECTIVE_XSS, REFERRER]

    # These directives do not fallback to default-src
    NO_FALLBACK = [BASE_URI, FORM_ACTION, FRAME_ANCESTORS, PLUGIN_TYPES,
                   REPORT_URI, SANDBOX, REFLECTIVE_XSS, REFERRER]

    def __init__(self, header_name, header_value):
        self._content_policies = defaultdict(list)
        self._header_name = None
        self._header_value = None
        self.header_name = header_name
        self.header_value = header_value

    @property
    def header_name(self):
        return self._header_name

    @header_name.setter
    def header_name(self, value):
        """ Setter for the header name """
        if value.lower() not in self.HEADERS:
            # We allow it, but maybe log it? For now, standard behavior.
            self._header_name = value.lower()
        else:
            self._header_name = value.lower()

    @property
    def header_value(self):
        return self._header_value

    @header_value.setter
    def header_value(self, value):
        """ Sets the header value and parses it """
        self._header_value = value.lower()
        self._parse_header()

    def _parse_header(self):
        """ Splits the header on ';' then subsequently on whitespace """
        for policy in self._header_value.split(";"):
            if not len(policy):
                continue  # Skip blanks
            directive, sources = self._unpack_policy(*policy.strip().split(" "))
            self[directive] = sources

    def _unpack_policy(self, directive, *content_sources):
        """ Used to unpack the directive name and directives """
        return directive, [src.strip() for src in content_sources]

    def is_deprecated_header(self):
        """ Check for X-WebKit-CSP or X-Content-Security-Policy """
        return self.header_name.startswith('x')

    def is_report_only_mode(self):
        return self.header_name.endswith("report-only")

    def iteritems(self):
        """ Similar to a dictionary, iterates tuples of key/value pairs """
        for key in self.CONTENT_DIRECTIVES:
            yield (key, self[key],)

    def __setitem__(self, key, value):
        if key not in self.CONTENT_DIRECTIVES:
            # In python 3, print is a function. Using rlog for warnings might be better but 
            # let's just ignore or add to custom directives if we wanted strictness.
            # raise ValueError("Unknown directive '%s'" % key)
            pass 
        
        if isinstance(value, list):
            self._content_policies[key].extend(value)
        elif isinstance(value, str):
            self._content_policies[key].append(value)
        else:
            pass
            # raise ValueError("Expected list or basestring")

    def __getitem__(self, key):
        """
        Get the policy or return default-src if the policy isn't in NO_FALLBACK
        """
        if key in self._content_policies:
            return self._content_policies[key]
        elif key not in self.NO_FALLBACK:
            return self._content_policies[DEFAULT_SRC]
        return None

    def __contains__(self, item):
        if item not in self.NO_FALLBACK and item in self.CONTENT_DIRECTIVES:
            return True
        else:
            return item in self._content_policies

    def __iter__(self):
        for key in self.CONTENT_DIRECTIVES:
            yield key

# --- Checks ---

def make_issue(name, severity, confidence, detail, remediation, url, directive=None, bypass=None):
    return {
        "name": name,
        "severity": severity,
        "confidence": confidence,
        "detail": detail,
        "remediation": remediation,
        "url": url,
        "directive": directive,
        "bypass": bypass
    }

def deprecatedHeaderCheck(csp, url):
    issues = []
    if csp.is_deprecated_header():
        issues.append(make_issue(
            name="Deprecated Header",
            severity="Medium",
            confidence="Certain",
            detail="The site uses a deprecated CSP header",
            remediation="Change the server response header to `Content-Security-Policy'",
            url=url
        ))
    return issues

def reportOnlyHeaderCheck(csp, url):
    issues = []
    if csp.is_report_only_mode():
        issues.append(make_issue(
            name="Report Only Header",
            severity="High",
            confidence="Certain",
            detail="The site uses a CSP in report-only mode",
            remediation="Change the server response header to `Content-Security-Policy'",
            url=url
        ))
    return issues

def unsafeContentSourceCheck(csp, url):
    issues = []
    for directive in [SCRIPT_SRC, STYLE_SRC]:
        sources = csp[directive]
        if sources:
            if UNSAFE_EVAL in sources or UNSAFE_INLINE in sources:
                issues.append(make_issue(
                    name=f"Unsafe Content Source: {directive}",
                    severity="High",
                    confidence="Certain",
                    detail="This content security policy allows for unsafe content sources",
                    remediation="Refactor the website to remove inline JavaScript and CSS",
                    url=url,
                    directive=directive
                ))
    return issues

def wildcardContentSourceCheck(csp, url):
    issues = []
    for directive, sources in csp.iteritems():
        if sources is None:
            continue
        if any(src == "*" for src in sources):
            issues.append(make_issue(
                name=f"Wildcard Content Source: {directive}",
                severity="Medium",
                confidence="Certain",
                detail=f"The {directive} CSP directive does not enforce any restrictions on what origins content can be loaded from.",
                remediation="Remove all wildcards from the content security policy.",
                url=url,
                directive=directive
            ))
    return issues

def wildcardSubdomainContentSourceCheck(csp, url):
    issues = []
    for directive, sources in csp.iteritems():
        if sources is None:
            continue
        if any("*" in src and 5 <= len(src) for src in sources):
             issues.append(make_issue(
                name=f"Wildcard Subdomain Content Source: {directive}",
                severity="Low",
                confidence="Certain",
                detail="Wildcard subdomains expose additional attack surface, since an attacker can potentially leverage a vulnerability in any subdomain to to bypass the CSP.",
                remediation="Avoid use of wildcard subdomains in CSP directives.",
                url=url,
                directive=directive
            ))
    return issues

def nonceSourceCheck(csp, url):
    issues = []
    for directive, sources in csp.iteritems():
        if sources is None:
            continue
        if any(src.startswith("'nonce-") for src in sources):
             issues.append(make_issue(
                name="Nonce Content Source",
                severity="Informational",
                confidence="Certain",
                detail="This site uses nonces to secure inline content",
                remediation="Refactor the website to disallow all inline content, and remove nonce content sources from the CSP.",
                url=url,
                directive=directive
            ))
    return issues

def insecureContentSourceCheck(csp, url):
    issues = []
    for directive, sources in csp.iteritems():
        if sources is None:
            continue
        for src in sources:
            if src == HTTP or (src != '*' and urlparse(src).scheme in ["http", "ws"]):
                issues.append(make_issue(
                    name=f"Insecure Content Source: {directive}",
                    severity="High",
                    confidence="Certain",
                    detail=f"The content directive {directive} allows resources to be loaded over insecure network protocols.",
                    remediation="Restrict content sources to only use secure protocols such as https:// and wss://.",
                    url=url,
                    directive=directive
                ))
    return issues

def missingDirectiveCheck(csp, url):
    issues = []
    for directive in ContentSecurityPolicy.NO_FALLBACK:
        if directive not in csp:
             issues.append(make_issue(
                name=f"Missing CSP Directive: {directive}",
                severity="Medium",
                confidence="Certain",
                detail=f"The {directive} content directive does not fallback to default-src, if no content sources are explicitly set it will default to completely open.",
                remediation=f"Explicitly set a {directive} directive in your content policy.",
                url=url,
                directive=directive
            ))
    return issues

def weakDefaultSourceCheck(csp, url):
    issues = []
    sources = csp[DEFAULT_SRC]
    if sources:
        # Check if sources are restrictive enough.
        # Original logic: if contentSource not in [SELF, NONE, HTTPS]: fail
        for contentSource in sources:
            if contentSource not in [SELF, NONE, HTTPS]:
                issues.append(make_issue(
                    name="Weak default-src Directive",
                    severity="Medium",
                    confidence="Certain",
                    detail="The default content source should be as restrictive as possible the content policy for this website does not restrict the default source to either 'none' 'self' (and 'https:').",
                    remediation="Set the default-src to either 'self' or preferrably 'none'. If the default source is set to 'self' also consider adding 'https:' to ensure resources are loaded over a secure network connection.",
                    url=url
                ))
                break
    return issues

def _bypassCheckDirective(csp, directive, knownBypasses):
    bypasses = []
    sources = csp[directive]
    if not sources:
        return bypasses
        
    for src in sources:
        if src.startswith("'") or src in [HTTP, HTTPS, DATA, BLOB]:
            continue  # We only care about domains

        # Iterate over all bypasses and check if `src' allows loading
        # content from `domain' if so, we have a bypass!
        for domain, payload in knownBypasses:
            if csp_match_domains(src, domain):
                bypasses.append((domain, payload,))
    return bypasses

def knownBypassCheck(csp, url):
    issues = []
    for directive, knownBypasses in CSP_KNOWN_BYPASSES.items():
        bypasses = _bypassCheckDirective(csp, directive, knownBypasses)
        for bypass in bypasses:
             issues.append(make_issue(
                name=f"Known CSP Bypass: {directive}",
                severity="High",
                confidence="Certain",
                detail=f"A known bypass exists in the '{directive}' directive for the domain '{bypass[0]}'. {bypass[1]}",
                remediation=f"Remove the content source '{bypass[0]}' domain from your '{directive}' CSP directive.",
                url=url,
                directive=directive,
                bypass=bypass
            ))
    return issues

CHECKS = [
    deprecatedHeaderCheck,
    reportOnlyHeaderCheck,
    unsafeContentSourceCheck,
    wildcardContentSourceCheck,
    wildcardSubdomainContentSourceCheck,
    insecureContentSourceCheck,
    nonceSourceCheck,
    missingDirectiveCheck,
    weakDefaultSourceCheck,
    knownBypassCheck,
]

def parseContentSecurityPolicy(header_name, header_value, url):
    csp = ContentSecurityPolicy(header_name, header_value)
    issues = []
    for check in CHECKS:
        try:
            issues.extend(check(csp, url))
        except Exception as e:
            rlog(f"Error in CSP check {check.__name__}: {e}", level="error")
    return issues


# --- Scheduled Function ---

async def py_check_csp_bypass(event, scheduled_md):
    scanner_name = event["name"]
    async with get_unprocessed_entries(scanner_name, event, match_storage_fn=web_match_storage) as unscanned:
        flows = [i["entry"] for i in unscanned.values()]
        if not flows:
            return

        site_results = defaultdict(list)
        
        for flow in flows:
            if not flow_in_scope(flow):
                continue

            # In rcn-server, headers are usually "response-headers" (dict)
            resp_headers = flow.get("response-headers")
            if not resp_headers:
                continue

            url = flow.get("url")
            if not url:
                continue
                
            findings = []
            
            # Helper to check headers
            # Normalize keys to lowercase for check
            
            headers_to_check = []
            if isinstance(resp_headers, dict):
                headers_to_check = resp_headers.items()
            elif isinstance(resp_headers, list):
                # list of [key, val]
                headers_to_check = resp_headers
            
            for k, v in headers_to_check:
                if k.lower() in ContentSecurityPolicy.HEADERS:
                    # Found a CSP header
                    f = parseContentSecurityPolicy(k, v, url)
                    if f:
                        findings.extend(f)
            
            if findings:
                # Add findings as notes to the flow
                # We need the app to get the storage to add the note
                site = urlparse(url).netloc
                st = storage()
                app = get_app_by_site(st, site)
                
                if not app:
                    app = get_app_by_site(st, site)
                
                if app:
                    flow_id = flow.get("id")
                    
                    for finding in findings:
                        key = "csp-" + finding["name"]
                        value = f"Severity: {finding['severity']}\nDetail: {finding['detail']}\nRemediation: {finding['remediation']}"
                        if finding.get("bypass"):
                            value += f"\nBypass: {finding['bypass']}"
                            
                        global_add_annotation(entry_id=flow_id, storage_name="app-flows", key=key, value=value, parent_id=app['id'])
                    
                    rlog(f"Added {len(findings)} CSP annotations to flow {flow_id} for {site}", level="info")



