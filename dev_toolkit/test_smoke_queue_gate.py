from dev_toolkit import smoke


def test_smoke_queue_gate_is_zero_tolerance_for_new_failures() -> None:
    assert smoke._no_new_queue_failures(failed_now=10, baseline_failed=10)
    assert not smoke._no_new_queue_failures(failed_now=11, baseline_failed=10)


def test_smoke_queue_gate_ignores_external_failed_count_cleanup() -> None:
    assert smoke._new_failed_delta(failed_now=9, baseline_failed=10) == 0
    assert smoke._no_new_queue_failures(failed_now=9, baseline_failed=10)
