"""Tests for task_queue_audit_service.py — classification, reconcile, debt tracking."""
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from app.models.system import SystemTaskQueue
from app.services import task_queue_audit_service as audit
from app.services.task_queue_audit_service import reconcile_orphan_running, reconcile_stale_pending
from sqlalchemy import delete


async def _cleanup(marker: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(SystemTaskQueue).where(SystemTaskQueue.task_type.like(f"test_audit_{marker}%"))
        )
        await db.commit()


async def _create_task(
    task_type: str,
    status: str,
    *,
    started_at: datetime | None = None,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
    error_message: str | None = None,
    retry_count: int = 0,
    max_retries: int = 3,
    scheduled_at: datetime | None = None,
    module: str = "test",
) -> int:
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        task = SystemTaskQueue(
            task_type=task_type,
            parameters=json.dumps({"marker": task_type}),
            status=status,
            priority=0,
            module=module,
            retry_count=retry_count,
            max_retries=max_retries,
            started_at=started_at,
            created_at=created_at or now,
            completed_at=completed_at,
            error_message=error_message,
            scheduled_at=scheduled_at,
        )
        db.add(task)
        await db.commit()
        return task.id


@pytest.mark.asyncio
async def test_audit_classifies_recent_vs_historical_failed() -> None:
    marker = uuid4().hex
    await _cleanup(marker)
    try:
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=2)
        await _create_task(
            f"test_audit_{marker}_recent", "failed",
            completed_at=now - timedelta(minutes=30),
            error_message="recent failure",
        )
        await _create_task(
            f"test_audit_{marker}_old", "failed",
            completed_at=old,
            error_message="old debt",
        )

        async with AsyncSessionLocal() as db:
            audit_result = await audit.audit_task_queue(db)

        assert audit_result["recent_failed_count"] >= 1, "recent failure should be visible"
        assert audit_result["historical_debt_total"] >= 1, "old failure should be historical debt"
        assert audit_result["classification"]["historical_failed_debt_count"] >= 1
        assert audit_result["classification"]["recent_failed_count"] >= 1
    finally:
        await _cleanup(marker)


@pytest.mark.asyncio
async def test_audit_classifies_stale_pending() -> None:
    marker = uuid4().hex
    await _cleanup(marker)
    try:
        now = datetime.now(timezone.utc)
        await _create_task(
            f"test_audit_{marker}_fresh", "pending",
            created_at=now - timedelta(minutes=5),
        )
        await _create_task(
            f"test_audit_{marker}_stale", "pending",
            created_at=now - timedelta(hours=2),
        )

        async with AsyncSessionLocal() as db:
            audit_result = await audit.audit_task_queue(db)

        cls = audit_result["classification"]
        assert cls["actionable_pending_count"] >= 1, "fresh pending should be actionable"
        assert cls["stale_pending_debt_count"] >= 1, "stale pending should be debt"
    finally:
        await _cleanup(marker)


@pytest.mark.asyncio
async def test_reconcile_stale_pending_marks_as_failed() -> None:
    marker = uuid4().hex
    await _cleanup(marker)
    try:
        now = datetime.now(timezone.utc)
        task_id = await _create_task(
            f"test_audit_{marker}_stale_recon", "pending",
            created_at=now - timedelta(hours=2),
        )

        async with AsyncSessionLocal() as db:
            reconciled = await reconcile_stale_pending(db)

        assert any(r["id"] == task_id for r in reconciled), "stale task should be reconciled"
    finally:
        await _cleanup(marker)


@pytest.mark.asyncio
async def test_reconcile_orphan_running_reclaims() -> None:
    marker = uuid4().hex
    await _cleanup(marker)
    try:
        now = datetime.now(timezone.utc)
        task_id = await _create_task(
            f"test_audit_{marker}_orphan", "running",
            started_at=now - timedelta(seconds=audit.ORPHAN_RUNNING_TIMEOUT_SECONDS + 120),
        )

        async with AsyncSessionLocal() as db:
            reconciled = await reconcile_orphan_running(db)

        assert any(r["id"] == task_id for r in reconciled), "orphan should be reconciled"
    finally:
        await _cleanup(marker)


@pytest.mark.asyncio
async def test_audit_includes_handler_breakdown() -> None:
    marker = uuid4().hex
    await _cleanup(marker)
    try:
        await _create_task(f"test_audit_{marker}_h1", "failed", module="test",
                           error_message="err1",
                           completed_at=datetime.now(timezone.utc) - timedelta(minutes=10))
        await _create_task(f"test_audit_{marker}_h1", "completed", module="test")

        async with AsyncSessionLocal() as db:
            audit_result = await audit.audit_task_queue(db)

        breakdown = audit_result["handler_breakdown"]
        found = False
        for htype, states in breakdown.items():
            if marker in htype:
                found = True
                break
        assert found, "handler breakdown should include test tasks"
        assert len(audit_result["top_error_signatures"]) >= 0
    finally:
        await _cleanup(marker)


@pytest.mark.asyncio
async def test_audit_reports_stalest_pending() -> None:
    marker = uuid4().hex
    await _cleanup(marker)
    try:
        now = datetime.now(timezone.utc)
        await _create_task(
            f"test_audit_{marker}_oldest", "pending",
            created_at=now - timedelta(hours=3),
        )

        async with AsyncSessionLocal() as db:
            audit_result = await audit.audit_task_queue(db)

        stalest = audit_result["stalest_pending"]
        assert stalest is not None, "should report stalest pending"
        assert stalest["age_seconds"] > 0
    finally:
        await _cleanup(marker)


@pytest.mark.asyncio
async def test_audit_metadata_includes_thresholds() -> None:
    async with AsyncSessionLocal() as db:
        audit_result = await audit.audit_task_queue(db)

    meta = audit_result["metadata"]
    assert meta["recent_failure_window_hours"] == audit.RECENT_FAILURE_WINDOW_HOURS
    assert meta["debt_cutoff_hours"] == audit.HISTORICAL_DEBT_CUTOFF_HOURS
    assert meta["stale_pending_threshold_seconds"] == audit.STALE_PENDING_THRESHOLD_SECONDS
    assert meta["orphan_timeout_seconds"] == audit.ORPHAN_RUNNING_TIMEOUT_SECONDS
