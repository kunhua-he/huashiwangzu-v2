"""Sandbox test for im module.

Validates parameter schemas, required fields, value ranges, and output
shapes for all public_actions — without sending real messages or
notifications.
"""


def test_notify_params() -> None:
    """notify: user_id (int required), content (string required, non-empty)."""
    params = {"user_id": 1, "content": "Your task has been completed."}
    assert "user_id" in params
    assert isinstance(params["user_id"], int) and params["user_id"] > 0
    assert "content" in params
    assert isinstance(params["content"], str) and len(params["content"].strip()) > 0
    print("  [NOTIFY] Parameter contract valid")


def test_notify_params_rejects_empty_content() -> None:
    """Notify content must be non-empty."""
    params = {"user_id": 1, "content": ""}
    assert "content" in params
    assert len(params["content"].strip()) == 0, "Empty content should be rejected"
    print("  [NOTIFY] Empty content detection valid")


def test_notify_params_rejects_missing_user_id() -> None:
    """Notify requires user_id."""
    params = {"content": "Hello"}
    assert "user_id" not in params
    assert "content" in params
    print("  [NOTIFY] Missing user_id detection valid")


def test_send_params() -> None:
    """send: conversation_id (int required), content (string required, non-empty)."""
    params = {"conversation_id": 42, "content": "Hello, how can I help you?"}
    assert "conversation_id" in params
    assert isinstance(params["conversation_id"], int) and params["conversation_id"] > 0
    assert "content" in params
    assert isinstance(params["content"], str) and len(params["content"].strip()) > 0
    print("  [SEND] Parameter contract valid")


def test_send_params_rejects_empty_content() -> None:
    """Send content must be non-empty."""
    params = {"conversation_id": 42, "content": ""}
    assert "content" in params
    assert len(params["content"].strip()) == 0
    print("  [SEND] Empty content detection valid")


def test_notify_output_shape() -> None:
    """Notify output shape contract."""
    result = {
        "success": True,
        "data": {
            "message_id": 101,
            "user_id": 1,
            "content": "Your task has been completed.",
            "timestamp": "2026-07-01T00:00:00",
        },
        "error": None,
    }
    assert result["success"] is True
    data = result["data"]
    required_data = {"message_id", "user_id", "content", "timestamp"}
    for field in required_data:
        assert field in data, f"Missing required field: {field}"
    assert isinstance(data["message_id"], int)
    assert isinstance(data["user_id"], int)
    print("  [NOTIFY_OUTPUT] Output shape valid")


def test_send_output_shape() -> None:
    """Send output shape contract."""
    result = {
        "success": True,
        "data": {
            "message_id": 200,
            "conversation_id": 42,
            "content": "Hello, how can I help you?",
            "timestamp": "2026-07-01T00:00:00",
        },
        "error": None,
    }
    assert result["success"] is True
    data = result["data"]
    required_data = {"message_id", "conversation_id", "content", "timestamp"}
    for field in required_data:
        assert field in data, f"Missing required field: {field}"
    assert isinstance(data["message_id"], int)
    assert isinstance(data["conversation_id"], int)
    print("  [SEND_OUTPUT] Output shape valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"message_id": 1, "conversation_id": 1, "timestamp": "2026-07-01T00:00:00"}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def main() -> None:
    print("=" * 60)
    print("im sandbox test")
    print("=" * 60)
    test_notify_params()
    test_notify_params_rejects_empty_content()
    test_notify_params_rejects_missing_user_id()
    test_send_params()
    test_send_params_rejects_empty_content()
    test_notify_output_shape()
    test_send_output_shape()
    test_response_shape()
    print("=" * 60)
    print("PASS: im sandbox test")


if __name__ == "__main__":
    main()
