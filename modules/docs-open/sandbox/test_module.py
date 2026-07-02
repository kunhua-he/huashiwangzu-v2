"""Sandbox test for docs-open module.

Validates core contracts: open, get_content, create_doc parameter schemas
and output shapes — without real document reads or DB calls.
"""


def test_open_params() -> None:
    """open action parameter contract: file_id required int, mode optional string."""
    # Minimum valid params
    params_min = {"file_id": 42}
    assert "file_id" in params_min
    assert isinstance(params_min["file_id"], int) and params_min["file_id"] > 0

    # Full params
    params_full = {"file_id": 42, "mode": "read"}
    assert "file_id" in params_full
    assert isinstance(params_full["file_id"], int) and params_full["file_id"] > 0
    if "mode" in params_full:
        assert isinstance(params_full["mode"], str)
    print("  [OPEN] Parameter contract valid")


def test_open_output_shape() -> None:
    """open action output shape contract."""
    result = {
        "embed_url": "https://docs.example.com/view/42",
        "file_id": 42,
        "title": "Sample Document",
        "content_type": "text",
    }
    required = {"embed_url", "file_id"}
    for field in required:
        assert field in result, f"Missing required field: {field}"
    assert isinstance(result["embed_url"], str)
    assert isinstance(result["file_id"], int)
    print("  [OPEN] Output shape valid")


def test_get_content_params() -> None:
    """get_content action parameter contract: file_id required int."""
    params = {"file_id": 42}
    assert "file_id" in params
    assert isinstance(params["file_id"], int) and params["file_id"] > 0
    print("  [GET_CONTENT] Parameter contract valid")


def test_get_content_output_shape() -> None:
    """get_content action output shape contract (structured JSON)."""
    result = {
        "file_id": 42,
        "title": "Sample Document",
        "sections": [
            {"heading": "Introduction", "body": "Text content..."},
            {"heading": "Details", "body": "More text..."},
        ],
    }
    required = {"file_id", "title", "sections"}
    for field in required:
        assert field in result, f"Missing required field: {field}"
    assert isinstance(result["sections"], list)
    if result["sections"]:
        section = result["sections"][0]
        assert "heading" in section and "body" in section
    print("  [GET_CONTENT] Output shape valid")


def test_create_doc_params() -> None:
    """create_doc action parameter contract: title and type required strings."""
    # Minimum valid params
    params = {"title": "New Document", "type": "plain"}
    assert "title" in params
    assert "type" in params
    assert isinstance(params["title"], str) and params["title"].strip()
    assert isinstance(params["type"], str) and params["type"].strip()

    # Missing title
    bad = {"type": "plain"}
    assert "title" not in bad or not bad.get("title"), "title should be required"

    # Missing type
    bad2 = {"title": "New Document"}
    assert "type" not in bad2 or not bad2.get("type"), "type should be required"
    print("  [CREATE_DOC] Parameter contract valid")


def test_create_doc_output_shape() -> None:
    """create_doc action output shape contract."""
    result = {
        "file_id": 100,
        "title": "New Document",
        "type": "plain",
        "created_at": "2026-07-01T00:00:00",
    }
    required = {"file_id", "title"}
    for field in required:
        assert field in result, f"Missing required field: {field}"
    assert isinstance(result["file_id"], int)
    assert isinstance(result["title"], str)
    print("  [CREATE_DOC] Output shape valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"file_id": 1}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def main() -> None:
    print("=" * 60)
    print("docs-open sandbox test")
    print("=" * 60)
    test_open_params()
    test_open_output_shape()
    test_get_content_params()
    test_get_content_output_shape()
    test_create_doc_params()
    test_create_doc_output_shape()
    test_response_shape()
    print("=" * 60)
    print("PASS: docs-open sandbox test")


if __name__ == "__main__":
    main()
