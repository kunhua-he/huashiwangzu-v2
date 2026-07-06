from datetime import datetime, timezone

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
    assert config.max_lanes_per_process == task_worker.DEFAULT_MAX_LANES_PER_PROCESS
    assert config.poll_interval_seconds == 2.0
    assert config.running_timeout_seconds == 1200
    assert config.config_reload_seconds == 5.0
    assert config.reclaim_running_on_startup is False
    assert config.startup_reclaim_min_age_seconds == 10


def test_task_worker_config_clamps_lane_count() -> None:
    config = task_worker._parse_worker_config({
        "worker_lanes_per_process": 999,
        "max_lanes_per_process": 24,
        "poll_interval_seconds": 0,
        "running_timeout_seconds": 1,
        "config_reload_seconds": 0,
        "reclaim_running_on_startup": "true",
        "startup_reclaim_min_age_seconds": -1,
    })

    assert config.worker_lanes_per_process == 24
    assert config.max_lanes_per_process == 24
    assert config.poll_interval_seconds == 0.2
    assert config.running_timeout_seconds == 60
    assert config.config_reload_seconds == 1.0
    assert config.reclaim_running_on_startup is True
    assert config.startup_reclaim_min_age_seconds == 0


def test_task_worker_config_allows_zero_lanes_for_hot_pause() -> None:
    config = task_worker._parse_worker_config({"worker_lanes_per_process": 0})

    assert config.worker_lanes_per_process == 0


def test_task_worker_config_clamps_dynamic_max_lanes() -> None:
    config = task_worker._parse_worker_config({
        "worker_lanes_per_process": 999,
        "max_lanes_per_process": 999,
    })

    assert config.worker_lanes_per_process == task_worker.ABSOLUTE_MAX_LANES_PER_PROCESS
    assert config.max_lanes_per_process == task_worker.ABSOLUTE_MAX_LANES_PER_PROCESS


def test_task_worker_result_serializer_handles_datetime() -> None:
    serialized = task_worker._serialize_task_result({
        "status": "done",
        "completed_at": datetime(2026, 7, 7, 1, 30, tzinfo=timezone.utc),
    })

    assert serialized is not None
    assert '"status": "done"' in serialized
    assert "2026-07-07 01:30:00+00:00" in serialized


def test_active_task_snapshot_is_stable_and_sorted() -> None:
    original = dict(task_worker._lane_current_task_ids)
    try:
        task_worker._lane_current_task_ids.clear()
        task_worker._lane_current_task_ids.update({3: 200, 1: 100, 2: 100})

        assert task_worker._active_task_ids_snapshot() == [100, 200]
    finally:
        task_worker._lane_current_task_ids.clear()
        task_worker._lane_current_task_ids.update(original)
