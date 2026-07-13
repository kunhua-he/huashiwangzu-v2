"""Executor lifecycle recovery tests for the Dispatcher."""
from __future__ import annotations

import json
import os
from datetime import timedelta
from time import perf_counter
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from app.models.system import SystemTaskQueue, TaskAttemptMetric
from app.services import event_bus, task_dispatcher, task_worker
from sqlalchemy import delete, select


async def _cleanup(task_type: str) -> None:
    async with AsyncSessionLocal() as db:
        ids = select(SystemTaskQueue.id).where(SystemTaskQueue.task_type == task_type)
        await db.execute(delete(TaskAttemptMetric).where(TaskAttemptMetric.task_id.in_(ids)))
        await db.execute(delete(SystemTaskQueue).where(SystemTaskQueue.task_type == task_type))
        await db.commit()


@pytest.mark.asyncio
async def test_executor_settles_handler_with_fenced_lease_and_outbox_event() -> None:
    task_type = f"test_dispatch_executor_{uuid4().hex}"
    task_id = 0

    async def handler(params: dict) -> dict:
        return {"status": "done", "marker": params["marker"]}

    task_worker.register_task_handler(task_type, handler)
    try:
        await event_bus._ensure_event_log_table()
        async with AsyncSessionLocal() as db:
            task = await task_dispatcher.publish_task(
                db, task_type=task_type, module="test", owner_id=None,
                body={"marker": task_type}, requested_by="test", trigger="pytest",
            )
            task.status = "running"
            task.lease_token = "lease-test"
            task.lease_owner = "pytest"
            task.lease_expires_at = task_dispatcher._now() + timedelta(seconds=60)
            task.attempt = 1
            task_id = int(task.id)
            await db.commit()

        assert await task_dispatcher.execute_claimed_task(task_id, "lease-test") == 0
        async with AsyncSessionLocal() as db:
            task = await db.get(SystemTaskQueue, task_id)
            assert task is not None
            assert task.status == "completed"
            assert task.lease_token is None
            assert json.loads(task.result or "{}") == {"status": "done", "marker": task_type}
            event_id = await db.scalar(
                select(TaskAttemptMetric.id).where(TaskAttemptMetric.task_id == task_id).limit(1)
            )
            # Executor completion records the outbox; process metrics are added
            # by its supervising Dispatcher, so direct executor mode has none.
            assert event_id is None
            outbox_id = await db.scalar(
                __import__("sqlalchemy").text(
                    "SELECT id FROM framework_event_log WHERE dedup_key = :key"
                ),
                {"key": f"task-settled:{task_id}:lease-test"},
            )
            assert outbox_id is not None
    finally:
        if task_id:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    __import__("sqlalchemy").text(
                        "DELETE FROM framework_event_log WHERE dedup_key LIKE :prefix"
                    ),
                    {"prefix": f"task-settled:{task_id}:%"},
                )
                await db.commit()
        await _cleanup(task_type)


@pytest.mark.asyncio
async def test_stale_lease_does_not_override_new_owner() -> None:
    task_type = f"test_dispatch_fence_{uuid4().hex}"
    task_worker.register_task_handler(task_type, task_worker._echo_handler)
    try:
        async with AsyncSessionLocal() as db:
            task = await task_dispatcher.publish_task(
                db, task_type=task_type, module="test", owner_id=None,
                body={"marker": task_type}, requested_by="test", trigger="pytest",
            )
            task.status = "running"
            task.lease_token = "new-owner"
            task.lease_expires_at = task_dispatcher._now() + timedelta(seconds=60)
            task_id = int(task.id)
            await db.commit()
        assert await task_dispatcher.execute_claimed_task(task_id, "old-owner") == 2
        async with AsyncSessionLocal() as db:
            task = await db.get(SystemTaskQueue, task_id)
            assert task is not None and task.lease_token == "new-owner" and task.status == "running"
    finally:
        await _cleanup(task_type)


@pytest.mark.asyncio
async def test_executor_exit_releases_lease_and_writes_attempt_metric() -> None:
    task_type = f"test_dispatch_executor_exit_{uuid4().hex}"
    task_worker.register_task_handler(task_type, task_worker._echo_handler)
    try:
        async with AsyncSessionLocal() as db:
            task = await task_dispatcher.publish_task(
                db, task_type=task_type, module="test", owner_id=None,
                body={"marker": task_type}, requested_by="test", trigger="pytest",
            )
            task.status = "running"
            task.attempt = 1
            task.lease_token = "crash-lease"
            task.lease_owner = "pytest"
            task.lease_expires_at = task_dispatcher._now() + timedelta(seconds=60)
            task_id = int(task.id)
            await db.commit()

        claim = task_dispatcher.ClaimedLease(
            task_id=task_id,
            lease_token="crash-lease",
            task_type=task_type,
            lane_key="general",
            stage_key=task_type,
            attempt=1,
        )
        state = task_dispatcher.ExecutorState(
            claim=claim,
            process=SimpleNamespace(pid=os.getpid(), returncode=137),
            started_at=task_dispatcher._now(),
            started_perf=perf_counter(),
            rss_start_mb=None,
            rss_peak_mb=None,
            cpu_start_seconds=None,
            io_start=None,
            last_heartbeat=task_dispatcher._now(),
        )
        async with AsyncSessionLocal() as db:
            await task_dispatcher._mark_executor_exit(db, state, 137)
            task = await db.get(SystemTaskQueue, task_id)
            metric = await db.scalar(select(TaskAttemptMetric).where(TaskAttemptMetric.task_id == task_id))
            assert task is not None and task.status == "pending" and task.lease_token is None
            assert metric is not None and metric.status == "executor_exit" and metric.exit_code == 137
    finally:
        await _cleanup(task_type)


def test_qwen_chunk_embedding_contract_exposes_watchdog() -> None:
    from modules.knowledge.backend.services.chunk_embedding_service import resolve_chunk_embedding_contract

    contract = resolve_chunk_embedding_contract("qwen3-embedding-8b")
    assert contract["dimensions"] == 4096
    assert contract["vector_store"] == "kb_chunk_embeddings"
    assert contract["watchdog"] == "qwen3-embedding-8b"
