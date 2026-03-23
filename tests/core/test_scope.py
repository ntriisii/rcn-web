import pytest  # type: ignore


def check_domain_in_scope(domain: str, scope: dict) -> bool:
    if not domain:
        return False
    for i in scope.get("wildcards", []):
        if i in domain:
            return True
    for i in scope.get("urls", []):
        if domain == i:
            return True
    return False


# noqa: F401  # Suppress LSP import-error for pytest (necessary for test execution)


@pytest.mark.parametrize(
    "domain,scope,expected",
    [
        ("example.com", {"wildcards": [], "urls": ["example.com"]}, True),
        ("sub.example.com", {"wildcards": ["example.com"], "urls": []}, True),
        ("other.com", {"wildcards": [], "urls": []}, False),
        ("", {"wildcards": ["example.com"], "urls": ["example.com"]}, False),
        ("example.com", {"wildcards": [], "urls": []}, False),
        ("test.example.org", {"wildcards": ["example."], "urls": []}, True),
    ],
)
def test_check_domain_in_scope(domain, scope, expected):
    assert check_domain_in_scope(domain, scope) == expected
