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


def test_task_worker_treats_nested_success_false_as_failure() -> None:
    failed, error = task_worker._result_is_semantic_failure({
        "success": True,
        "data": {"success": False, "error": "nested failed"},
    })

    assert failed is True
    assert error == "nested failed"


def test_task_worker_treats_legacy_code_nonzero_as_failure() -> None:
    failed, error = task_worker._result_is_semantic_failure({
        "code": 1,
        "msg": "legacy tool failed",
    })

    assert failed is True
    assert error == "legacy tool failed"


def test_task_worker_config_defaults_are_safe() -> None:
    config = task_worker._parse_worker_config({})

    assert config.worker_lanes_per_process == 1
    assert config.poll_interval_seconds == 2.0
    assert config.running_timeout_seconds == 1200
    assert config.config_reload_seconds == 5.0


def test_task_worker_config_clamps_lane_count() -> None:
    config = task_worker._parse_worker_config({
        "worker_lanes_per_process": 999,
        "poll_interval_seconds": 0,
        "running_timeout_seconds": 1,
        "config_reload_seconds": 0,
    })

    assert config.worker_lanes_per_process == task_worker.MAX_LANES_PER_PROCESS
    assert config.poll_interval_seconds == 0.2
    assert config.running_timeout_seconds == 60
    assert config.config_reload_seconds == 1.0


def test_task_worker_config_allows_zero_lanes_for_hot_pause() -> None:
    config = task_worker._parse_worker_config({"worker_lanes_per_process": 0})

    assert config.worker_lanes_per_process == 0
