import asyncio

from dev_toolkit import smoke


def test_smoke_queue_gate_is_zero_tolerance_for_new_failures() -> None:
    assert smoke._no_new_queue_failures(failed_now=10, baseline_failed=10)
    assert not smoke._no_new_queue_failures(failed_now=11, baseline_failed=10)


def test_smoke_queue_gate_ignores_external_failed_count_cleanup() -> None:
    assert smoke._new_failed_delta(failed_now=9, baseline_failed=10) == 0
    assert smoke._no_new_queue_failures(failed_now=9, baseline_failed=10)


def test_smoke_samples_queue_before_business_steps(monkeypatch) -> None:
    order: list[str] = []

    async def fake_probe(method: str, path: str, body: dict | None = None, role: str = "admin") -> dict:
        if path == "/api/tasks/worker/status":
            order.append("queue_status")
            return {"data": {"data": {"failed": 7, "pending": 1, "oldest_waiting_seconds": 0}}}
        return {"data": {"success": True, "data": {}}}

    async def fake_group() -> None:
        order.append("business")

    async def fake_settle(baseline_pending: int = 0, timeout: int = 30) -> dict:
        order.append(f"settle:{baseline_pending}")
        return {"failed": 7, "pending": baseline_pending, "oldest_waiting_seconds": 0}

    async def fake_flush() -> int:
        return 0

    monkeypatch.setattr(smoke, "probe", fake_probe)
    for name in ("health_check", "test_a", "test_b", "test_c", "test_d", "test_e"):
        monkeypatch.setattr(smoke, name, fake_group)
    monkeypatch.setattr(smoke, "_await_queue_settle", fake_settle)
    monkeypatch.setattr(smoke, "_flush_pending_deletions", fake_flush)
    monkeypatch.setenv("SMOKE_SKIP_UI", "1")
    smoke.results.clear()
    smoke._pending_deletions.clear()

    asyncio.run(smoke.main())

    assert order[0] == "queue_status"
    assert order.index("queue_status") < order.index("business")
