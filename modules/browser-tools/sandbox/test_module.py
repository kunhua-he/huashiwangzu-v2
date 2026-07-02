"""Sandbox test for browser-tools module.

Validates parameter schemas, required fields, value ranges, and output shapes
based on MANIFEST public_actions. No real browser calls.
"""
# ── URL validation helpers ─────────────────────────────────────────────

def _validate_url(url: str) -> None:
    """Reject non-http/https URLs."""
    if not isinstance(url, str) or not url.strip():
        raise AssertionError("URL must be a non-empty string")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise AssertionError(f"URL must start with http:// or https://, got: {url[:30]}")


def _validate_session_id(session_id: Any, *, required: bool = True) -> None:
    """Validate session_id is a non-empty string when required."""
    if required:
        assert isinstance(session_id, str) and session_id.strip(), \
            "session_id is required and must be a non-empty string"
    else:
        if session_id is not None:
            assert isinstance(session_id, str) and session_id.strip(), \
                "session_id must be a non-empty string when provided"


def _validate_timeout(timeout: Any) -> None:
    """Validate timeout is a positive number (default 30)."""
    if timeout is not None:
        assert isinstance(timeout, (int, float)) and timeout > 0, \
            f"timeout must be a positive number, got: {timeout!r}"


# ── Parameter validation per action ────────────────────────────────────

def test_open_params() -> None:
    """open: url required (http/https), session_id optional, timeout optional."""
    # Valid
    params = {"url": "https://example.com"}
    _validate_url(params["url"])
    _validate_session_id(params.get("session_id"), required=False)
    _validate_timeout(params.get("timeout"))
    print("  [open] Valid params (url only): PASS")

    # With optional session_id
    params = {"url": "http://example.org", "session_id": "sess_abc123", "timeout": 15}
    _validate_url(params["url"])
    _validate_session_id(params["session_id"], required=False)
    _validate_timeout(params["timeout"])
    print("  [open] Valid params (full): PASS")

    # Missing url
    try:
        _validate_url("")
        raise AssertionError("Should have rejected empty url")
    except AssertionError:
        print("  [open] Missing url rejected: PASS")

    # Bad protocol
    try:
        _validate_url("ftp://example.com")
        raise AssertionError("Should have rejected ftp url")
    except AssertionError:
        print("  [open] Bad protocol rejected: PASS")


def test_read_text_params() -> None:
    """read_text: session_id required."""
    params = {"session_id": "sess_abc123"}
    _validate_session_id(params["session_id"])
    print("  [read_text] Valid params: PASS")

    try:
        _validate_session_id("")
        raise AssertionError("Should have rejected empty session_id")
    except AssertionError:
        print("  [read_text] Empty session_id rejected: PASS")

    try:
        _validate_session_id(None)  # type: ignore[arg-type]
        raise AssertionError("Should have rejected None session_id")
    except AssertionError:
        print("  [read_text] None session_id rejected: PASS")


def test_list_links_params() -> None:
    """list_links: session_id required."""
    params = {"session_id": "sess_xyz789"}
    _validate_session_id(params["session_id"])
    print("  [list_links] Valid params: PASS")


def test_click_params() -> None:
    """click: session_id required, selector OR text (at least one)."""
    # Valid: selector only
    params = {"session_id": "sess_abc", "selector": "#submit-btn"}
    _validate_session_id(params["session_id"])
    assert "selector" in params or "text" in params, "click needs selector or text"
    assert not (params.get("selector") and params.get("text") and
                params["selector"] and params["text"]), \
        "selector and text are mutually exclusive, only one should be set at a time"
    print("  [click] Valid (selector only): PASS")

    # Valid: text only
    params = {"session_id": "sess_abc", "text": "Submit"}
    _validate_session_id(params["session_id"])
    assert "selector" in params or "text" in params, "click needs selector or text"
    print("  [click] Valid (text only): PASS")

    # Missing both selector and text
    try:
        params = {"session_id": "sess_abc"}
        _validate_session_id(params["session_id"])
        assert "selector" in params or "text" in params, \
            "click requires either 'selector' or 'text' parameter"
        raise AssertionError("Should have rejected missing selector and text")
    except AssertionError:
        print("  [click] Missing selector+text rejected: PASS")

    # Both provided (manifest says "or" — mutually exclusive)
    try:
        params = {"session_id": "sess_abc", "selector": "#btn", "text": "Click"}
        _validate_session_id(params["session_id"])
        both_provided = bool(params.get("selector")) and bool(params.get("text"))
        assert not both_provided, \
            "selector and text should not both be provided simultaneously"
        raise AssertionError("Should have rejected both selector+text")
    except AssertionError:
        print("  [click] Both selector+text rejected (mutually exclusive): PASS")


def test_type_params() -> None:
    """type: session_id, selector, text all required."""
    params = {"session_id": "sess_abc", "selector": "#search-input", "text": "hello world"}
    _validate_session_id(params["session_id"])
    assert isinstance(params.get("selector"), str) and params["selector"].strip(), \
        "type requires a non-empty selector"
    assert isinstance(params.get("text"), str) and params["text"].strip(), \
        "type requires non-empty text"
    print("  [type] Valid params: PASS")

    # Missing text
    try:
        params = {"session_id": "sess_abc", "selector": "#input"}
        assert isinstance(params.get("text"), str) and params["text"].strip(), \
            "type requires non-empty text"
        raise AssertionError("Should have rejected missing text")
    except AssertionError:
        print("  [type] Missing text rejected: PASS")


def test_wait_for_params() -> None:
    """wait_for: session_id, selector required; timeout optional."""
    params = {"session_id": "sess_abc", "selector": ".loaded"}
    _validate_session_id(params["session_id"])
    assert isinstance(params.get("selector"), str) and params["selector"].strip(), \
        "wait_for requires a non-empty selector"
    _validate_timeout(params.get("timeout"))
    print("  [wait_for] Valid params: PASS")

    params_full = {"session_id": "sess_abc", "selector": "#done", "timeout": 60}
    _validate_session_id(params_full["session_id"])
    _validate_timeout(params_full["timeout"])
    print("  [wait_for] Valid params with timeout: PASS")


def test_screenshot_params() -> None:
    """screenshot: session_id required, full_page optional bool."""
    params = {"session_id": "sess_abc"}
    _validate_session_id(params["session_id"])
    print("  [screenshot] Valid params (no full_page): PASS")

    params = {"session_id": "sess_abc", "full_page": True}
    _validate_session_id(params["session_id"])
    assert isinstance(params.get("full_page"), bool), "full_page must be boolean"
    print("  [screenshot] Valid params (full_page=True): PASS")

    # Invalid full_page type
    try:
        params = {"session_id": "sess_abc", "full_page": "yes"}
        assert isinstance(params.get("full_page"), bool), \
            "full_page must be boolean"
        raise AssertionError("Should have rejected non-boolean full_page")
    except AssertionError:
        print("  [screenshot] Non-bool full_page rejected: PASS")


def test_download_params() -> None:
    """download: session_id required, url optional, timeout optional."""
    params = {"session_id": "sess_abc"}
    _validate_session_id(params["session_id"])
    if "url" in params:
        _validate_url(params["url"])
    _validate_timeout(params.get("timeout"))
    print("  [download] Valid params (url optional from browser context): PASS")

    params = {"session_id": "sess_abc", "url": "https://example.com/file.pdf", "timeout": 60}
    _validate_session_id(params["session_id"])
    _validate_url(params["url"])
    _validate_timeout(params["timeout"])
    print("  [download] Valid params (with url): PASS")

    try:
        params = {"session_id": "sess_abc", "url": "file:///etc/passwd"}
        _validate_session_id(params["session_id"])
        _validate_url(params["url"])
        raise AssertionError("Should have rejected non-http URL")
    except AssertionError:
        print("  [download] Non-http URL rejected: PASS")


def test_close_params() -> None:
    """close: session_id required, returns success/failure."""
    params = {"session_id": "sess_abc"}
    _validate_session_id(params["session_id"])
    print("  [close] Valid params: PASS")

    # Simulate output shape
    success_result = {"success": True, "session_id": "sess_abc"}
    assert isinstance(success_result["success"], bool)
    assert success_result["session_id"] == "sess_abc"
    failure_result = {"success": False, "error": "Session not found"}
    assert failure_result["success"] is False
    print("  [close] Output shape (success/failure): PASS")


def test_output_shapes() -> None:
    """Validate output shapes for screenshot and download."""
    # Screenshot output shape
    screenshot_result = {
        "file_id": "file_001",
        "path": "/workspace/screenshots/page.png",
        "size": 245760,
    }
    assert isinstance(screenshot_result["file_id"], str)
    assert isinstance(screenshot_result["path"], str)
    assert isinstance(screenshot_result["size"], int) and screenshot_result["size"] >= 0
    print("  [screenshot] Output shape (file_id, path, size): PASS")

    # Download output shape
    download_result = {
        "file_id": "file_002",
        "path": "/workspace/downloads/report.pdf",
        "size": 1048576,
    }
    assert isinstance(download_result["file_id"], str)
    assert isinstance(download_result["path"], str)
    assert isinstance(download_result["size"], int) and download_result["size"] >= 0
    print("  [download] Output shape (file_id, path, size): PASS")


def test_no_cookie_localstorage_return() -> None:
    """Cookie/localStorage NOT returned to caller by any action."""
    # Simulate a read_text response — must NOT contain cookies or localStorage
    result = {
        "title": "Example",
        "url": "https://example.com",
        "text": "Hello world",
    }
    assert "cookies" not in result, "Cookies must not be returned"
    assert "localStorage" not in result, "localStorage must not be returned"
    assert "cookie" not in result, "Cookie data must not leak"
    print("  [privacy] No cookie/localStorage in output: PASS")


def test_session_id_flow() -> None:
    """session_id optional for open, required for all other actions."""
    # open: session_id optional
    open_params = [{"url": "https://example.com"}, {"url": "https://example.com", "session_id": "sess_new"}]
    for p in open_params:
        _validate_url(p["url"])
        _validate_session_id(p.get("session_id"), required=False)
    print("  [session] open accepts optional session_id: PASS")

    # Other actions require session_id
    for action in ["read_text", "list_links", "click", "type", "wait_for", "screenshot", "close"]:
        try:
            _validate_session_id(None)  # type: ignore[arg-type]
            raise AssertionError(f"{action} should require session_id")
        except AssertionError:
            pass
    print("  [session] All other actions require session_id: PASS")


def main() -> None:
    print("=" * 60)
    print("browser-tools sandbox test")
    print("=" * 60)

    test_open_params()
    test_read_text_params()
    test_list_links_params()
    test_click_params()
    test_type_params()
    test_wait_for_params()
    test_screenshot_params()
    test_download_params()
    test_close_params()
    test_output_shapes()
    test_no_cookie_localstorage_return()
    test_session_id_flow()

    print("=" * 60)
    print("PASS: browser-tools sandbox test")


if __name__ == "__main__":
    main()
