"""Persistent event bus with retry support for cross-module events.

Replaces the in-memory-only event system with persistence-backed delivery.
Events are stored in the framework_event_log table and can survive worker
restarts. Failed handlers are retried with configurable backoff.

Handler signature: async def(payload: dict, caller: str, caller_role: str) -> dict
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from app.database import AsyncSessionLocal
from app.services.semantic_failure import semantic_failure_reason

logger = logging.getLogger("v2.event_bus")

EventHandler = Callable[[dict, str, str], Awaitable[dict]]

_event_handlers: dict[str, list[dict]] = {}
"""event_name -> [{module_key, handler}]"""

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10
PROCESSING_TIMEOUT_SECONDS = 1200


def _semantic_failure(handler_result: object) -> str | None:
    """Return a stable error message when a handler result represents failure."""
    return semantic_failure_reason(handler_result)


def _build_handler_result(module_key: str, handler_result: object) -> dict:
    error_msg = _semantic_failure(handler_result)
    result = {
        "module_key": module_key,
        "success": error_msg is None,
        "result": handler_result,
    }
    if error_msg:
        result["error"] = error_msg
    return result


def register_module_event_handler(
    event_name: str,
    handler: EventHandler,
    module_key: str,
) -> None:
    """Register a module to receive event_name events.

    Idempotent: last registration wins for the same module+event pair.
    """
    if event_name not in _event_handlers:
        _event_handlers[event_name] = []
    existing = [e for e in _event_handlers[event_name] if e["module_key"] == module_key]
    if existing:
        existing[0]["handler"] = handler
    else:
        _event_handlers[event_name].append({
            "module_key": module_key,
            "handler": handler,
        })
    logger.debug("Registered event handler: module=%s event=%s", module_key, event_name)


async def _ensure_event_log_table():
    """Create the framework_event_log table if it doesn't exist."""
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("""
                CREATE TABLE IF NOT EXISTS framework_event_log (
                    id BIGSERIAL PRIMARY KEY,
                    event_name VARCHAR(128) NOT NULL,
                    payload JSONB DEFAULT '{}'::jsonb,
                    caller VARCHAR(128) DEFAULT '',
                    caller_role VARCHAR(32) DEFAULT 'viewer',
                    status VARCHAR(32) DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    last_error TEXT,
                    next_retry_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    processing_started_at TIMESTAMPTZ,
                    module_results JSONB DEFAULT '[]'::jsonb
                )
            """))
            await db.execute(text("""
                ALTER TABLE framework_event_log
                ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ
            """))
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_framework_event_log_status
                ON framework_event_log(status)
            """))
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_framework_event_log_next_retry
                ON framework_event_log(next_retry_at)
                WHERE status = 'pending'
            """))
            await db.commit()
    except Exception as e:
        logger.warning("Event log table creation failed (may already exist): %s", e)


async def emit_module_event(
    event_name: str,
    payload: dict,
    caller: str,
    caller_role: str = "viewer",
    persist: bool = True,
) -> list[dict]:
    """Emit an event to registered handlers.

    If persist=True, the event is stored in framework_event_log before
    handler execution. Handlers are called sequentially; a single handler
    failure does not prevent others from running. Failed handlers are
    queued for retry.
    """
    handlers = _event_handlers.get(event_name, [])
    if not handlers:
        logger.debug("No handlers registered for event '%s'", event_name)
        return []

    # Persist the event as processing so retry workers cannot replay normal
    # first delivery while handlers are still running.
    log_id = None
    if persist:
        log_id = await _persist_event(event_name, payload, caller, caller_role)

    results: list[dict] = []
    for entry in handlers:
        handler_result = None
        try:
            handler_result = await entry["handler"](payload, caller, caller_role)
            result = _build_handler_result(entry["module_key"], handler_result)
            if not result["success"]:
                logger.warning(
                    "Event '%s' handler for module '%s' returned failure: %s",
                    event_name, entry["module_key"], result.get("error"),
                )
        except Exception as exc:
            logger.warning(
                "Event '%s' handler for module '%s' failed: %s",
                event_name, entry["module_key"], exc,
            )
            result = {
                "module_key": entry["module_key"],
                "success": False,
                "error": str(exc),
            }
        results.append(result)

    # Update event log with results
    if log_id:
        await _update_event_log(log_id, results)

    return results


async def _persist_event(event_name: str, payload: dict, caller: str, caller_role: str) -> int | None:
    """Persist an event to the database log."""
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            r = await db.execute(
                text("""
                    INSERT INTO framework_event_log
                        (event_name, payload, caller, caller_role, status, max_retries, processing_started_at)
                    VALUES (:event_name, CAST(:payload AS jsonb), :caller, :caller_role, 'processing', :max_retries, NOW())
                    RETURNING id
                """),
                {
                    "event_name": event_name,
                    "payload": json.dumps(payload, ensure_ascii=False, default=str),
                    "caller": caller,
                    "caller_role": caller_role,
                    "max_retries": MAX_RETRIES,
                },
            )
            await db.commit()
            log_id = r.scalar()
            return log_id
    except Exception as e:
        logger.warning("Failed to persist event '%s': %s", event_name, e)
        return None


async def _update_event_log(log_id: int, results: list[dict]) -> None:
    """Update the event log with handler results."""
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            has_failures = any(not r.get("success") for r in results)
            status = "pending" if has_failures else "completed"
            last_error = next(
                (
                    str(r.get("error"))
                    for r in results
                    if isinstance(r, dict) and r.get("success") is not True and r.get("error")
                ),
                None,
            )
            next_retry_at = (
                datetime.now(timezone.utc) + timedelta(seconds=RETRY_DELAY_SECONDS)
                if has_failures else None
            )
            completed_at = datetime.now(timezone.utc) if status == "completed" else None
            await db.execute(
                text("""
                    UPDATE framework_event_log
                    SET status = :new_status,
                        module_results = CAST(:results AS jsonb),
                        last_error = :last_error,
                        completed_at = :completed_at,
                        next_retry_at = :next_retry_at,
                        processing_started_at = NULL
                    WHERE id = :id
                """),
                {
                    "new_status": status,
                    "results": json.dumps(results, ensure_ascii=False, default=str),
                    "last_error": last_error,
                    "completed_at": completed_at,
                    "next_retry_at": next_retry_at,
                    "id": log_id,
                },
            )
            await db.commit()
    except Exception as e:
        logger.warning("Failed to update event log %d: %s", log_id, e)


async def get_event_log(
    event_name: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query the event log for debugging and replay."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        conditions = ["1=1"]
        params: dict = {}
        if event_name:
            conditions.append("event_name = :event_name")
            params["event_name"] = event_name
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions)
        r = await db.execute(
            text(f"""
                SELECT id, event_name, payload, caller, caller_role, status,
                       retry_count, max_retries, last_error, next_retry_at,
                       created_at, completed_at, module_results
                FROM framework_event_log
                WHERE {where_clause}
                ORDER BY id DESC
                LIMIT :limit
            """),
            {**params, "limit": limit},
        )
        rows = r.all()
        return [
            {
                "id": row[0],
                "event_name": row[1],
                "payload": row[2],
                "caller": row[3],
                "caller_role": row[4],
                "status": row[5],
                "retry_count": row[6],
                "max_retries": row[7],
                "last_error": row[8],
                "next_retry_at": row[9].isoformat() if row[9] else None,
                "created_at": row[10].isoformat() if row[10] else None,
                "completed_at": row[11].isoformat() if row[11] else None,
                "module_results": row[12],
            }
            for row in rows
        ]


def _failed_modules(module_results: object) -> set[str]:
    if not isinstance(module_results, list):
        return set()
    return {
        str(row.get("module_key"))
        for row in module_results
        if isinstance(row, dict) and row.get("success") is not True and row.get("module_key")
    }


async def retry_failed_events() -> int:
    """Retry all events that are due for retry. Called by scheduler."""
    retried = 0
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(
            text("""
                UPDATE framework_event_log
                SET status = 'pending', processing_started_at = NULL,
                    last_error = COALESCE(last_error, 'Processing lease expired')
                WHERE status = 'processing'
                  AND processing_started_at < NOW() - (:timeout_seconds * INTERVAL '1 second')
            """),
            {"timeout_seconds": PROCESSING_TIMEOUT_SECONDS},
        )
        r = await db.execute(
            text("""
                UPDATE framework_event_log
                SET status = 'processing', processing_started_at = NOW()
                WHERE id IN (
                    SELECT id
                    FROM framework_event_log
                    WHERE status = 'pending'
                      AND retry_count < max_retries
                      AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                    ORDER BY id ASC
                    LIMIT 20
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, event_name, payload, caller, caller_role, retry_count,
                          max_retries, module_results
            """),
        )
        rows = r.all()
        await db.commit()

        for row in rows:
            log_id = row[0]
            event_name = row[1]
            payload = row[2]
            caller = row[3]
            caller_role = row[4]
            retry_count = row[5]
            max_retries = row[6]
            module_results = row[7]

            handlers = _event_handlers.get(event_name, [])
            all_success = True
            last_error = None
            failed_modules = _failed_modules(module_results)
            retry_results = list(module_results or []) if isinstance(module_results, list) else []

            for entry in handlers:
                if failed_modules and entry["module_key"] not in failed_modules:
                    continue
                try:
                    handler_result = await entry["handler"](payload, caller, caller_role)
                    result = _build_handler_result(entry["module_key"], handler_result)
                    if not result["success"]:
                        all_success = False
                        last_error = str(result.get("error") or "Handler returned failure")
                        logger.warning(
                            "Retry %d for event '%s' handler '%s' returned failure: %s",
                            retry_count + 1,
                            event_name,
                            entry["module_key"],
                            last_error,
                        )
                    retry_results = [
                        item for item in retry_results
                        if not (isinstance(item, dict) and item.get("module_key") == entry["module_key"])
                    ]
                    retry_results.append(result)
                except Exception as exc:
                    all_success = False
                    last_error = str(exc)
                    retry_results = [
                        item for item in retry_results
                        if not (isinstance(item, dict) and item.get("module_key") == entry["module_key"])
                    ]
                    retry_results.append({
                        "module_key": entry["module_key"],
                        "success": False,
                        "error": last_error,
                    })
                    logger.warning("Retry %d for event '%s' handler '%s' failed: %s",
                                   retry_count + 1, event_name, entry["module_key"], exc)

            new_retry_count = retry_count + 1
            if all_success:
                await db.execute(
                    text("""
                        UPDATE framework_event_log
                        SET status = 'completed', retry_count = :retry_count,
                            last_error = NULL, next_retry_at = NULL,
                            completed_at = NOW(), processing_started_at = NULL,
                            module_results = CAST(:results AS jsonb)
                        WHERE id = :id
                    """),
                    {
                        "retry_count": new_retry_count,
                        "results": json.dumps(retry_results, ensure_ascii=False, default=str),
                        "id": log_id,
                    },
                )
                retried += 1
            else:
                next_retry = datetime.now(timezone.utc) + timedelta(seconds=RETRY_DELAY_SECONDS * (2 ** new_retry_count))
                if new_retry_count >= max_retries:
                    await db.execute(
                        text("""
                            UPDATE framework_event_log
                            SET status = 'failed', retry_count = :retry_count,
                                last_error = :last_error, next_retry_at = NULL,
                                processing_started_at = NULL,
                                module_results = CAST(:results AS jsonb)
                            WHERE id = :id
                        """),
                        {"retry_count": new_retry_count, "last_error": last_error,
                         "results": json.dumps(retry_results, ensure_ascii=False, default=str), "id": log_id},
                    )
                else:
                    await db.execute(
                        text("""
                            UPDATE framework_event_log
                            SET status = 'pending', retry_count = :retry_count,
                                last_error = :last_error, next_retry_at = :next_retry,
                                processing_started_at = NULL,
                                module_results = CAST(:results AS jsonb)
                            WHERE id = :id
                        """),
                        {"retry_count": new_retry_count, "last_error": last_error,
                         "next_retry": next_retry,
                         "results": json.dumps(retry_results, ensure_ascii=False, default=str), "id": log_id},
                    )
        await db.commit()

    if retried:
        logger.info("Retried %d events", retried)
    return retried


async def replay_event(log_id: int) -> dict | None:
    """Replay a specific event from the log. Returns the results."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        r = await db.execute(
            text("""
                SELECT id, event_name, payload, caller, caller_role
                FROM framework_event_log
                WHERE id = :id
            """),
            {"id": log_id},
        )
        row = r.one_or_none()
        if not row:
            return None

        log_id_val = row[0]
        event_name = row[1]
        payload = row[2]
        caller = row[3]
        caller_role = row[4]

        results = await emit_module_event(event_name, payload, caller, caller_role, persist=False)
        await _update_event_log(log_id_val, results)
        return {
            "event_name": event_name,
            "results": results,
        }
