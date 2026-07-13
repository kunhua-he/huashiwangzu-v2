import asyncio
import json
from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from app.services import event_bus
from sqlalchemy import text


async def _cleanup(event_name: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM framework_event_log WHERE event_name = :event_name"), {"event_name": event_name})
        await db.commit()


async def _insert_pending_event(event_name: str, module_results: list[dict] | None = None) -> int:
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            text("""
                INSERT INTO framework_event_log
                    (event_name, payload, caller, caller_role, status, retry_count,
                     max_retries, next_retry_at, module_results)
                VALUES (:event_name, CAST(:payload AS jsonb), 'test', 'admin', 'pending', 0,
                        3, NOW(), CAST(:module_results AS jsonb))
                RETURNING id
            """),
            {
                "event_name": event_name,
                "payload": json.dumps({"event_name": event_name}),
                "module_results": json.dumps(module_results or []),
            },
        )
        await db.commit()
        return int(row.scalar_one())


async def _get_event(log_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            text("""
                SELECT status, retry_count, module_results, last_error
                FROM framework_event_log
                WHERE id = :id
            """),
            {"id": log_id},
        )
        status, retry_count, module_results, last_error = row.one()
        return {
            "status": status,
            "retry_count": retry_count,
            "module_results": module_results,
            "last_error": last_error,
        }


@pytest.mark.asyncio
async def test_append_event_in_transaction_is_deduplicated_and_rolls_back() -> None:
    event_name = f"test.dispatcher.outbox.{uuid4().hex}"
    dedup_key = f"{event_name}:dedup"
    await event_bus._ensure_event_log_table()
    try:
        async with AsyncSessionLocal() as db:
            first_id = await event_bus.append_event_in_transaction(
                db,
                event_name=event_name,
                payload={"marker": event_name},
                caller="test",
                caller_role="admin",
                dedup_key=dedup_key,
            )
            second_id = await event_bus.append_event_in_transaction(
                db,
                event_name=event_name,
                payload={"marker": event_name},
                caller="test",
                caller_role="admin",
                dedup_key=dedup_key,
            )
            assert first_id == second_id
            await db.commit()
        async with AsyncSessionLocal() as db:
            count = await db.scalar(
                text("SELECT count(*) FROM framework_event_log WHERE dedup_key = :key"),
                {"key": dedup_key},
            )
            assert count == 1
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM framework_event_log WHERE dedup_key = :key"), {"key": dedup_key})
            await db.commit()


@pytest.mark.asyncio
async def test_concurrent_retry_claims_event_once() -> None:
    event_name = f"test.retry.once.{uuid4().hex}"
    await event_bus._ensure_event_log_table()
    await _cleanup(event_name)
    calls = 0

    async def handler(_payload: dict, _caller: str, _caller_role: str) -> dict:
        nonlocal calls
        await asyncio.sleep(0.05)
        calls += 1
        return {"ok": True}

    previous = event_bus._event_handlers.get(event_name)
    event_bus._event_handlers[event_name] = [{"module_key": "test-module", "handler": handler}]
    try:
        log_id = await _insert_pending_event(event_name)

        results = await asyncio.gather(*[event_bus.retry_failed_events() for _ in range(3)])

        event = await _get_event(log_id)
        assert calls == 1
        assert sum(results) >= 1
        assert event["status"] == "completed"
        assert event["retry_count"] == 1
    finally:
        if previous is None:
            event_bus._event_handlers.pop(event_name, None)
        else:
            event_bus._event_handlers[event_name] = previous
        await _cleanup(event_name)


@pytest.mark.asyncio
async def test_retry_only_replays_failed_handler() -> None:
    event_name = f"test.retry.failed_only.{uuid4().hex}"
    await event_bus._ensure_event_log_table()
    await _cleanup(event_name)
    calls = {"success": 0, "failed": 0}

    async def success_handler(_payload: dict, _caller: str, _caller_role: str) -> dict:
        calls["success"] += 1
        return {"already": "done"}

    async def failed_handler(_payload: dict, _caller: str, _caller_role: str) -> dict:
        calls["failed"] += 1
        return {"retried": True}

    previous = event_bus._event_handlers.get(event_name)
    event_bus._event_handlers[event_name] = [
        {"module_key": "success-module", "handler": success_handler},
        {"module_key": "failed-module", "handler": failed_handler},
    ]
    try:
        log_id = await _insert_pending_event(
            event_name,
            [
                {"module_key": "success-module", "success": True, "result": {"already": "done"}},
                {"module_key": "failed-module", "success": False, "error": "boom"},
            ],
        )

        retried = await event_bus.retry_failed_events()

        event = await _get_event(log_id)
        assert retried == 1
        assert calls == {"success": 0, "failed": 1}
        assert event["status"] == "completed"
        assert {row["module_key"]: row["success"] for row in event["module_results"]} == {
            "success-module": True,
            "failed-module": True,
        }
    finally:
        if previous is None:
            event_bus._event_handlers.pop(event_name, None)
        else:
            event_bus._event_handlers[event_name] = previous
        await _cleanup(event_name)


@pytest.mark.asyncio
async def test_emit_marks_handler_semantic_failure_pending() -> None:
    event_name = f"test.emit.semantic_failure.{uuid4().hex}"
    await event_bus._ensure_event_log_table()
    await _cleanup(event_name)

    async def handler(_payload: dict, _caller: str, _caller_role: str) -> dict:
        return {"success": False, "error": "semantic boom"}

    previous = event_bus._event_handlers.get(event_name)
    event_bus._event_handlers[event_name] = [{"module_key": "semantic-module", "handler": handler}]
    try:
        results = await event_bus.emit_module_event(event_name, {"id": event_name}, "test", "admin")
        logs = await event_bus.get_event_log(event_name=event_name, limit=1)

        assert results == [
            {
                "module_key": "semantic-module",
                "success": False,
                "result": {"success": False, "error": "semantic boom"},
                "error": "semantic boom",
            }
        ]
        assert logs[0]["status"] == "pending"
        assert logs[0]["last_error"] == "semantic boom"
        assert logs[0]["module_results"][0]["success"] is False
        assert logs[0]["module_results"][0]["error"] == "semantic boom"
    finally:
        if previous is None:
            event_bus._event_handlers.pop(event_name, None)
        else:
            event_bus._event_handlers[event_name] = previous
        await _cleanup(event_name)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        ({"success": True, "result": {"status": "failed", "error_message": "nested failed"}}, "nested failed"),
        ({"success": True, "data": {"status": "error", "reason": "inner reason"}}, "inner reason"),
    ],
)
async def test_emit_marks_nested_handler_semantic_failure_pending(payload: dict, expected_error: str) -> None:
    event_name = f"test.emit.nested_semantic_failure.{uuid4().hex}"
    await event_bus._ensure_event_log_table()
    await _cleanup(event_name)

    async def handler(_payload: dict, _caller: str, _caller_role: str) -> dict:
        return payload

    previous = event_bus._event_handlers.get(event_name)
    event_bus._event_handlers[event_name] = [{"module_key": "semantic-module", "handler": handler}]
    try:
        await event_bus.emit_module_event(event_name, {"id": event_name}, "test", "admin")
        logs = await event_bus.get_event_log(event_name=event_name, limit=1)

        assert logs[0]["status"] == "pending"
        assert logs[0]["last_error"] == expected_error
        assert logs[0]["module_results"][0]["success"] is False
        assert logs[0]["module_results"][0]["error"] == expected_error
    finally:
        if previous is None:
            event_bus._event_handlers.pop(event_name, None)
        else:
            event_bus._event_handlers[event_name] = previous
        await _cleanup(event_name)


@pytest.mark.asyncio
async def test_retry_preserves_semantic_failure_for_retry() -> None:
    event_name = f"test.retry.semantic_failure.{uuid4().hex}"
    await event_bus._ensure_event_log_table()
    await _cleanup(event_name)

    async def handler(_payload: dict, _caller: str, _caller_role: str) -> dict:
        return {"status": "failed", "error": "still broken"}

    previous = event_bus._event_handlers.get(event_name)
    event_bus._event_handlers[event_name] = [{"module_key": "semantic-module", "handler": handler}]
    try:
        log_id = await _insert_pending_event(
            event_name,
            [{"module_key": "semantic-module", "success": False, "error": "first failure"}],
        )

        retried = await event_bus.retry_failed_events()

        event = await _get_event(log_id)
        assert retried == 0
        assert event["status"] == "pending"
        assert event["retry_count"] == 1
        assert event["last_error"] == "still broken"
        assert event["module_results"][0]["success"] is False
        assert event["module_results"][0]["error"] == "still broken"
    finally:
        if previous is None:
            event_bus._event_handlers.pop(event_name, None)
        else:
            event_bus._event_handlers[event_name] = previous
        await _cleanup(event_name)
