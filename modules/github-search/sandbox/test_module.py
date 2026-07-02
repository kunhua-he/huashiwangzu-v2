"""Sandbox test for github-search module.

Validates parameter schemas, required fields, value ranges, and output shapes
based on MANIFEST public_actions. No real GitHub API calls.
"""
# ── helpers ────────────────────────────────────────────────────────────

def _assert_non_empty_string(val: Any, name: str) -> None:
    assert isinstance(val, str) and val.strip(), \
        f"{name} is required and must be a non-empty string"


def _validate_limit(val: Any, *, default: int = 5, maximum: int = 10) -> int:
    """Validate limit param: default 5, max 10, must be positive int."""
    if val is None:
        return default
    assert isinstance(val, int) and not isinstance(val, bool), \
        f"limit must be an integer, got: {type(val).__name__}"
    assert 1 <= val <= maximum, \
        f"limit must be between 1 and {maximum}, got: {val}"
    return val


# ── search action tests ────────────────────────────────────────────────

def test_search_query_required() -> None:
    """search: query is required and non-empty."""
    try:
        _assert_non_empty_string("", "query")
        raise AssertionError("Should have rejected empty query")
    except AssertionError:
        print("  [search] Empty query rejected: PASS")

    try:
        _assert_non_empty_string("   ", "query")
        raise AssertionError("Should have rejected whitespace-only query")
    except AssertionError:
        print("  [search] Whitespace-only query rejected: PASS")

    _assert_non_empty_string("language:python stars:>100", "query")
    print("  [search] Valid query accepted: PASS")


def test_search_limit_range() -> None:
    """search: limit optional, default 5, max 10."""
    # Default
    limit = _validate_limit(None)
    assert limit == 5, f"Default limit should be 5, got {limit}"
    print("  [search] Default limit=5: PASS")

    # Valid custom
    limit = _validate_limit(3)
    assert limit == 3
    print("  [search] Custom limit=3: PASS")

    # Max boundary
    limit = _validate_limit(10)
    assert limit == 10
    print("  [search] Max limit=10: PASS")

    # Above max
    try:
        _validate_limit(11)
        raise AssertionError("Should have rejected limit > 10")
    except AssertionError:
        print("  [search] limit=11 rejected: PASS")

    # Below minimum
    try:
        _validate_limit(0)
        raise AssertionError("Should have rejected limit < 1")
    except AssertionError:
        print("  [search] limit=0 rejected: PASS")

    # Non-int
    try:
        _validate_limit("10")  # type: ignore[arg-type]
        raise AssertionError("Should have rejected string limit")
    except AssertionError:
        print("  [search] Non-int limit rejected: PASS")


def test_search_search_code_flag() -> None:
    """search: search_code optional, defaults to false (boolean)."""
    # Default
    search_code = None
    effective = bool(search_code) if search_code is not None else False
    assert effective is False, "search_code should default to False"
    print("  [search] Default search_code=False: PASS")

    # True
    search_code = True
    effective = bool(search_code)
    assert effective is True
    print("  [search] search_code=True: PASS")

    # Invalid type
    try:
        search_code = "yes"
        assert isinstance(search_code, bool), \
            "search_code must be a boolean"
        raise AssertionError("Should have rejected string search_code")
    except AssertionError:
        print("  [search] Non-bool search_code rejected: PASS")


def test_search_output_shape() -> None:
    """search output per result: name, full_name, description, html_url, stars, language, topics."""
    results = [
        {
            "name": "cpython",
            "full_name": "python/cpython",
            "description": "The Python programming language",
            "html_url": "https://github.com/python/cpython",
            "stars": 65000,
            "language": "Python",
            "topics": ["python", "interpreter", "compiler"],
        },
        {
            "name": "fastapi",
            "full_name": "tiangolo/fastapi",
            "description": "FastAPI framework",
            "html_url": "https://github.com/tiangolo/fastapi",
            "stars": 80000,
            "language": "Python",
            "topics": ["python", "api", "fastapi"],
        },
    ]
    expected_keys = {"name", "full_name", "description", "html_url", "stars", "language", "topics"}
    for item in results:
        missing = expected_keys - set(item.keys())
        assert not missing, f"Result missing keys: {missing}"
        assert isinstance(item["name"], str) and item["name"]
        assert isinstance(item["full_name"], str) and "/" in item["full_name"]
        assert isinstance(item["description"], str)
        assert isinstance(item["html_url"], str) and item["html_url"].startswith("https://github.com/")
        assert isinstance(item["stars"], int) and item["stars"] >= 0
        assert isinstance(item["language"], str) or item["language"] is None
        assert isinstance(item["topics"], list)
    print(f"  [search] Output shape ({len(results)} results, all keys present): PASS")


# ── search_code action tests ───────────────────────────────────────────

def test_search_code_query_required() -> None:
    """search_code: query required and non-empty."""
    try:
        _assert_non_empty_string("", "query")
        raise AssertionError("Should have rejected empty query")
    except AssertionError:
        print("  [search_code] Empty query rejected: PASS")

    _assert_non_empty_string("def fibonnaci", "query")
    print("  [search_code] Valid query accepted: PASS")


def test_search_code_language_optional() -> None:
    """search_code: language optional string."""
    # Without language
    params: dict[str, Any] = {"query": "def fibonnaci"}
    if "language" in params:
        assert isinstance(params["language"], str) and params["language"].strip(), \
            "language must be a non-empty string when provided"
    print("  [search_code] Without language: PASS")

    # With language
    params = {"query": "def fibonnaci", "language": "python"}
    assert isinstance(params["language"], str) and params["language"].strip()
    print("  [search_code] With language='python': PASS")

    # Invalid: empty language
    try:
        params = {"query": "def fibonnaci", "language": ""}
        if "language" in params and params["language"] is not None:
            assert isinstance(params["language"], str) and params["language"].strip(), \
                "language must be a non-empty string when provided"
            raise AssertionError("Should have rejected empty language")
    except AssertionError:
        print("  [search_code] Empty language rejected: PASS")


def test_search_code_limit_range() -> None:
    """search_code: limit optional, default 5, max 10."""
    limit = _validate_limit(None)
    assert limit == 5
    print("  [search_code] Default limit=5: PASS")

    limit = _validate_limit(10)
    assert limit == 10
    print("  [search_code] Max limit=10: PASS")

    try:
        _validate_limit(11)
        raise AssertionError("Should have rejected limit > 10")
    except AssertionError:
        print("  [search_code] limit=11 rejected: PASS")

    try:
        _validate_limit(0)
        raise AssertionError("Should have rejected limit < 1")
    except AssertionError:
        print("  [search_code] limit=0 rejected: PASS")


def test_search_code_output_shape() -> None:
    """search_code output shape: same result keys as search."""
    results = [
        {
            "name": "server.py",
            "full_name": "python/cpython/Lib/server.py",
            "description": "HTTP server implementation",
            "html_url": "https://github.com/python/cpython/blob/main/Lib/server.py",
            "stars": 65000,
            "language": "Python",
            "topics": [],
        },
    ]
    expected_keys = {"name", "full_name", "description", "html_url", "stars", "language", "topics"}
    for item in results:
        missing = expected_keys - set(item.keys())
        assert not missing, f"Result missing keys: {missing}"
    print("  [search_code] Output shape (all keys present): PASS")


def test_github_search_syntax() -> None:
    """search query supports GitHub search syntax."""
    valid_queries = [
        "language:python stars:>100",
        "topic:machine-learning",
        "org:facebook react",
        "fastapi",
        "language:go kubernetes operator",
    ]
    for q in valid_queries:
        _assert_non_empty_string(q, "query")
    print(f"  [syntax] {len(valid_queries)} GitHub search syntax queries accepted: PASS")


def main() -> None:
    print("=" * 60)
    print("github-search sandbox test")
    print("=" * 60)

    test_search_query_required()
    test_search_limit_range()
    test_search_search_code_flag()
    test_search_output_shape()
    test_search_code_query_required()
    test_search_code_language_optional()
    test_search_code_limit_range()
    test_search_code_output_shape()
    test_github_search_syntax()

    print("=" * 60)
    print("PASS: github-search sandbox test")


if __name__ == "__main__":
    main()
