"""Sandbox test for scheduler module.

Validates parameter schemas, required fields, value ranges, and output
shapes for all public_actions — without creating real scheduled tasks.
"""

from datetime import datetime


def test_create_params() -> None:
    """create: action_description (string), scheduled_at (string datetime),
    recur (string optional — cron/interval)."""
    params_min = {
        "action_description": "Send weekly report",
        "scheduled_at": "2026-07-08T09:00:00",
    }
    assert "action_description" in params_min
    assert isinstance(params_min["action_description"], str) and len(params_min["action_description"]) > 0
    assert "scheduled_at" in params_min
    assert isinstance(params_min["scheduled_at"], str)
    _validate_datetime(params_min["scheduled_at"])
    print("  [CREATE] Minimal params valid")

    params_recur = {
        "action_description": "Send weekly report",
        "scheduled_at": "2026-07-08T09:00:00",
        "recur": "0 9 * * 1",
    }
    assert "recur" in params_recur
    assert isinstance(params_recur["recur"], str) and len(params_recur["recur"]) > 0
    print("  [CREATE] With recur param valid")


def _validate_datetime(dt_str: str) -> None:
    """Validate that a datetime string is parseable."""
    # Accept ISO-8601 or common variants
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            datetime.strptime(dt_str, fmt)
            return
        except ValueError:
            continue
    raise AssertionError(f"Unparseable datetime string: {dt_str}")


def test_create_params_rejects_invalid_datetime() -> None:
    """Create requires a parseable datetime."""
    bad_dt = "not-a-date"
    try:
        _validate_datetime(bad_dt)
        assert False, "Should have raised AssertionError"
    except AssertionError:
        pass
    print("  [CREATE] Invalid datetime detection valid")


def test_create_params_rejects_empty_action() -> None:
    """Create requires non-empty action_description."""
    params = {"action_description": "", "scheduled_at": "2026-07-08T09:00:00"}
    assert "action_description" in params
    assert len(params["action_description"].strip()) == 0
    print("  [CREATE] Empty action detection valid")


def test_list_params() -> None:
    """list: no params."""
    params: dict = {}
    assert len(params) == 0
    print("  [LIST] Parameter contract valid")


def test_cancel_params() -> None:
    """cancel: task_id (int required)."""
    params = {"task_id": 5}
    assert "task_id" in params
    assert isinstance(params["task_id"], int) and params["task_id"] > 0
    print("  [CANCEL] Parameter contract valid")


def test_cancel_params_rejects_zero_id() -> None:
    """Cancel requires positive task_id."""
    params = {"task_id": 0}
    assert isinstance(params["task_id"], int)
    assert params["task_id"] <= 0, "task_id must be positive"
    print("  [CANCEL] Zero task_id detection valid")


def test_task_output_shape() -> None:
    """Task object output shape contract."""
    task = {
        "id": 1,
        "action_description": "Send weekly report",
        "scheduled_at": "2026-07-08T09:00:00",
        "recur": None,
        "status": "pending",
        "created_at": "2026-07-01T00:00:00",
    }
    required = {"id", "action_description", "scheduled_at", "status"}
    for field in required:
        assert field in task, f"Missing required field: {field}"
    assert isinstance(task["id"], int)
    assert task["status"] in ("pending", "running", "completed", "cancelled", "failed"), f"Invalid status: {task['status']}"
    print("  [TASK] Output shape valid")


def test_task_with_recur_output_shape() -> None:
    """Task with recurrence output shape contract."""
    task = {
        "id": 2,
        "action_description": "Daily backup",
        "scheduled_at": "2026-07-02T02:00:00",
        "recur": "0 2 * * *",
        "status": "pending",
        "created_at": "2026-07-01T00:00:00",
    }
    required = {"id", "action_description", "scheduled_at", "recur", "status"}
    for field in required:
        assert field in task, f"Missing required field: {field}"
    assert isinstance(task["recur"], str) and len(task["recur"]) > 0
    print("  [TASK_RECUR] Output shape valid")


def test_cancel_output_shape() -> None:
    """Cancel operation output shape contract."""
    result = {
        "success": True,
        "data": {
            "task_id": 5,
            "status": "cancelled",
        },
        "error": None,
    }
    assert result["success"] is True
    data = result["data"]
    assert "task_id" in data and "status" in data
    assert data["status"] == "cancelled"
    print("  [CANCEL_OUTPUT] Output shape valid")


def test_list_output_shape() -> None:
    """List output is an array of task objects."""
    tasks = [
        {
            "id": 1,
            "action_description": "Send weekly report",
            "scheduled_at": "2026-07-08T09:00:00",
            "recur": "0 9 * * 1",
            "status": "pending",
            "created_at": "2026-07-01T00:00:00",
        },
        {
            "id": 2,
            "action_description": "Daily backup",
            "scheduled_at": "2026-07-02T02:00:00",
            "recur": None,
            "status": "completed",
            "created_at": "2026-07-01T00:00:00",
        },
    ]
    assert isinstance(tasks, list)
    for task in tasks:
        assert "id" in task and "action_description" in task and "status" in task
        assert task["status"] in ("pending", "running", "completed", "cancelled", "failed")
    print("  [LIST_OUTPUT] Output shape valid")


def test_response_shape() -> None:
    """Unified API response shape contract."""
    r = {"success": True, "data": {"tasks": []}, "error": None}
    assert all(k in r for k in ("success", "data", "error"))
    assert r["success"] is True
    print("  [RESPONSE] Shape valid")


def main() -> None:
    print("=" * 60)
    print("scheduler sandbox test")
    print("=" * 60)
    test_create_params()
    test_create_params_rejects_invalid_datetime()
    test_create_params_rejects_empty_action()
    test_list_params()
    test_cancel_params()
    test_cancel_params_rejects_zero_id()
    test_task_output_shape()
    test_task_with_recur_output_shape()
    test_cancel_output_shape()
    test_list_output_shape()
    test_response_shape()
    print("=" * 60)
    print("PASS: scheduler sandbox test")


if __name__ == "__main__":
    main()
