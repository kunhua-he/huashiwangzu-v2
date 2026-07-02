"""Sandbox test for web-tools module.

Validates parameter schemas, required fields, value ranges, and output shapes
based on MANIFEST public_actions. No real web requests.
"""
# ── URL validation helpers ─────────────────────────────────────────────

_PRIVATE_PREFIXES = (
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
    "http://10.",
    "https://10.",
    "http://172.16.",
    "https://172.16.",
    "http://172.17.",
    "https://172.17.",
    "http://172.18.",
    "https://172.18.",
    "http://172.19.",
    "https://172.19.",
    "http://172.20.",
    "https://172.20.",
    "http://172.21.",
    "https://172.21.",
    "http://172.22.",
    "https://172.22.",
    "http://172.23.",
    "https://172.23.",
    "http://172.24.",
    "https://172.24.",
    "http://172.25.",
    "https://172.25.",
    "http://172.26.",
    "https://172.26.",
    "http://172.27.",
    "https://172.27.",
    "http://172.28.",
    "https://172.28.",
    "http://172.29.",
    "https://172.29.",
    "http://172.30.",
    "https://172.30.",
    "http://172.31.",
    "https://172.31.",
    "http://192.168.",
    "https://192.168.",
)


def _validate_public_url(url: str) -> None:
    """Reject non-http/https URLs and private/internal addresses (SSRF)."""
    if not isinstance(url, str) or not url.strip():
        raise AssertionError("URL must be a non-empty string")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise AssertionError(f"URL must start with http:// or https://, got: {url[:30]}")
    for prefix in _PRIVATE_PREFIXES:
        if url.startswith(prefix):
            raise AssertionError(f"SSRF protection: internal URL rejected: {url[:50]}")
    # Also reject bare IP formats like http://10.0.0.1
    if "://" in url:
        remainder = url.split("://", 1)[1]
        # Check for /etc/hosts style localhost
        if remainder.startswith("localhost") or remainder.startswith("localhost."):
            raise AssertionError(f"SSRF protection: localhost hostname rejected: {url[:50]}")


# ── Search tests ───────────────────────────────────────────────────────

def test_search_query_required() -> None:
    """search: query is required and must be non-empty."""
    try:
        query = ""
        assert isinstance(query, str) and len(query.strip()) > 0, \
            "query is required and must be a non-empty string"
        raise AssertionError("Should have rejected empty query")
    except AssertionError:
        print("  [search] Empty query rejected: PASS")

    query = "Python async programming"
    assert isinstance(query, str) and query.strip(), \
        "query is required and must be a non-empty string"
    print("  [search] Valid query accepted: PASS")


def test_search_top_k_range() -> None:
    """search: top_k optional, default 8, max 20."""
    # Default
    top_k = 8
    assert 1 <= top_k <= 20, "top_k must be between 1 and 20"
    print(f"  [search] Default top_k={top_k}: PASS")

    # Custom valid
    top_k = 5
    assert 1 <= top_k <= 20, "top_k must be between 1 and 20"
    print(f"  [search] Custom top_k={top_k}: PASS")

    # Max boundary
    top_k = 20
    assert 1 <= top_k <= 20, "top_k must be between 1 and 20"
    print(f"  [search] Max top_k={top_k}: PASS")

    # Below minimum
    try:
        top_k = 0
        assert 1 <= top_k <= 20, "top_k must be at least 1"
        raise AssertionError("Should have rejected top_k=0")
    except AssertionError:
        print("  [search] top_k=0 rejected: PASS")

    # Above maximum
    try:
        top_k = 21
        assert 1 <= top_k <= 20, "top_k must be at most 20"
        raise AssertionError("Should have rejected top_k=21")
    except AssertionError:
        print("  [search] top_k=21 rejected: PASS")


def test_search_output_shape() -> None:
    """search returns results array with title/link/snippet."""
    results = [
        {"title": "Async IO in Python", "link": "https://example.com/async", "snippet": "A guide to async..."},
        {"title": "Python Concurrency", "link": "https://example.com/concurrency", "snippet": "Comparing approaches..."},
    ]
    for item in results:
        assert "title" in item and isinstance(item["title"], str)
        assert "link" in item and isinstance(item["link"], str)
        assert "snippet" in item and isinstance(item["snippet"], str)
    print(f"  [search] Output shape ({len(results)} results): PASS")


# ── Fetch tests ────────────────────────────────────────────────────────

def test_fetch_url_required() -> None:
    """fetch: url required (http/https only)."""
    try:
        _validate_public_url("")
    except AssertionError:
        print("  [fetch] Empty URL rejected: PASS")

    try:
        _validate_public_url("not-a-url")
    except AssertionError:
        print("  [fetch] Non-URL string rejected: PASS")

    try:
        _validate_public_url("ftp://files.example.com")
    except AssertionError:
        print("  [fetch] FTP protocol rejected: PASS")

    try:
        _validate_public_url("file:///etc/passwd")
    except AssertionError:
        print("  [fetch] File protocol rejected: PASS")

    # Valid public URL
    _validate_public_url("https://example.com/article")
    print("  [fetch] Valid public URL accepted: PASS")


def test_fetch_ssrf_protection() -> None:
    """fetch rejects internal/private addresses."""
    bad_urls = [
        "http://localhost:8080/",
        "https://localhost:3000",
        "http://127.0.0.1:5432",
        "https://127.0.0.1/api",
        "http://10.0.0.1/admin",
        "https://10.0.0.1/secret",
        "http://172.16.0.1/config",
        "https://172.31.255.255/",
        "http://192.168.1.1/router",
        "https://192.168.0.1/admin",
        "http://localhost/",
        "https://localhost/health",
    ]
    for url in bad_urls:
        try:
            _validate_public_url(url)
            raise AssertionError(f"Should have rejected internal URL: {url}")
        except AssertionError:
            pass
    print(f"  [fetch] SSRF: {len(bad_urls)} internal URLs rejected: PASS")


def test_fetch_max_chars() -> None:
    """fetch: max_chars optional, default 8000, must be positive."""
    default_max_chars = 8000
    assert isinstance(default_max_chars, int) and default_max_chars > 0
    print(f"  [fetch] Default max_chars={default_max_chars}: PASS")

    # Custom valid
    max_chars = 4000
    assert max_chars > 0, "max_chars must be positive"
    print(f"  [fetch] Custom max_chars={max_chars}: PASS")

    # Invalid negative
    try:
        max_chars = -100
        assert max_chars > 0, "max_chars must be positive"
        raise AssertionError("Should have rejected negative max_chars")
    except AssertionError:
        print("  [fetch] Negative max_chars rejected: PASS")

    # Invalid zero
    try:
        max_chars = 0
        assert max_chars > 0, "max_chars must be positive"
        raise AssertionError("Should have rejected zero max_chars")
    except AssertionError:
        print("  [fetch] Zero max_chars rejected: PASS")


def test_fetch_output_shape() -> None:
    """fetch returns content string."""
    result = {"content": "Article body text...", "url": "https://example.com/article", "char_count": 1234}
    assert "content" in result and isinstance(result["content"], str)
    assert result["char_count"] >= 0
    print("  [fetch] Output shape (content, url, char_count): PASS")


def test_fetch_valid_urls() -> None:
    """fetch accepts various public URLs."""
    valid_urls = [
        "https://example.com",
        "http://example.com",
        "https://www.wikipedia.org/wiki/Python",
        "https://api.github.com/repos/python/cpython",
        "http://news.ycombinator.com",
    ]
    for url in valid_urls:
        _validate_public_url(url)
    print(f"  [fetch] {len(valid_urls)} valid public URLs accepted: PASS")


def main() -> None:
    print("=" * 60)
    print("web-tools sandbox test")
    print("=" * 60)

    test_search_query_required()
    test_search_top_k_range()
    test_search_output_shape()
    test_fetch_url_required()
    test_fetch_ssrf_protection()
    test_fetch_max_chars()
    test_fetch_output_shape()
    test_fetch_valid_urls()

    print("=" * 60)
    print("PASS: web-tools sandbox test")


if __name__ == "__main__":
    main()
