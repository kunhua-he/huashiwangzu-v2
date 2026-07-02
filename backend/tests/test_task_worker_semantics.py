from app.services import task_worker


def test_task_worker_treats_skipped_as_successful_noop() -> None:
    failed, error = task_worker._result_is_semantic_failure({
        "status": "skipped",
        "reason": "source_file_deleted",
    })

    assert failed is False
    assert error is None


def test_task_worker_treats_failed_status_as_failure() -> None:
    failed, error = task_worker._result_is_semantic_failure({
        "status": "failed",
        "error": "slow tool failed",
    })

    assert failed is True
    assert error == "slow tool failed"


def test_task_worker_treats_success_false_as_failure() -> None:
    failed, error = task_worker._result_is_semantic_failure({
        "success": False,
        "error": "agent execution failed",
    })

    assert failed is True
    assert error == "agent execution failed"
