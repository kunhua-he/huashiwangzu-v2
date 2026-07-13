"""Regression tests for the single Dispatcher task contract."""
from __future__ import annotations

import asyncio
import inspect
from datetime import timedelta
from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from app.models.system import SystemTaskQueue
from app.services import task_dispatcher, task_worker
from sqlalchemy import delete, update


async def _cleanup(task_type: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(SystemTaskQueue).where(SystemTaskQueue.task_type == task_type))
        await db.commit()


@pytest.mark.asyncio
async def test_publish_uses_fixed_envelope_and_rejects_physical_path() -> None:
    task_type = f"test_dispatch_envelope_{uuid4().hex}"
    task_worker.register_task_handler(task_type, task_worker._echo_handler)
    try:
        async with AsyncSessionLocal() as db:
            task = await task_dispatcher.publish_task(
                db,
                task_type=task_type,
                module="test",
                owner_id=None,
                body={"file_id": 123, "marker": task_type},
                requested_by="test",
                trigger="pytest",
            )
            await db.commit()
            assert task_dispatcher.unpack_task_parameters(task.parameters) == {"file_id": 123, "marker": task_type}
            with pytest.raises(ValueError, match="physical file path"):
                await task_dispatcher.publish_task(
                    db,
                    task_type=task_type,
                    module="test",
                    owner_id=None,
                    body={"file_path": "/private/test.pdf"},
                    requested_by="test",
                    trigger="pytest",
                )
    finally:
        await _cleanup(task_type)


@pytest.mark.asyncio
async def test_concurrent_dispatchers_claim_one_task_once() -> None:
    task_type = f"test_dispatch_claim_{uuid4().hex}"
    task_worker.register_task_handler(task_type, task_worker._echo_handler)
    config = task_dispatcher.DispatcherConfig(
        max_executors=4,
        lane_limits={"general": 4},
        allowed_task_types=frozenset({task_type}),
    )
    try:
        async with AsyncSessionLocal() as db:
            await task_dispatcher.publish_task(
                db, task_type=task_type, module="test", owner_id=None,
                body={"marker": task_type}, requested_by="test", trigger="pytest",
            )
            await db.commit()

        async def claim(owner: str):
            async with AsyncSessionLocal() as db:
                return await task_dispatcher.claim_next_task(db, owner=owner, config=config)

        claims = await asyncio.gather(claim("one"), claim("two"))
        won = [claim for claim in claims if claim is not None]
        assert len(won) == 1
        async with AsyncSessionLocal() as db:
            task = await db.get(SystemTaskQueue, won[0].task_id)
            assert task is not None and task.status == "running"
            assert task.lease_token == won[0].lease_token
    finally:
        await _cleanup(task_type)


@pytest.mark.asyncio
async def test_stage_fairness_keeps_newer_stage_visible_beyond_backlog_scan_limit() -> None:
    task_type = f"test_dispatch_stage_fairness_{uuid4().hex}"
    lane_key = f"test_fairness_{uuid4().hex}"
    task_worker.register_task_handler(task_type, task_worker._echo_handler)
    config = task_dispatcher.DispatcherConfig(
        max_executors=2,
        lane_limits={lane_key: 2},
        allowed_task_types=frozenset({task_type}),
    )
    try:
        async with AsyncSessionLocal() as db:
            for index in range(70):
                await task_dispatcher.publish_task(
                    db,
                    task_type=task_type,
                    module="test",
                    owner_id=None,
                    body={"marker": f"graph-{index}"},
                    requested_by="test",
                    trigger="pytest",
                    stage_key="graph",
                    lane_key=lane_key,
                )
            await task_dispatcher.publish_task(
                db,
                task_type=task_type,
                module="test",
                owner_id=None,
                body={"marker": "profile"},
                requested_by="test",
                trigger="pytest",
                stage_key="profile",
                lane_key=lane_key,
            )
            await db.commit()

        async with AsyncSessionLocal() as db:
            first = await task_dispatcher.claim_next_task(db, owner="first", config=config)
            second = await task_dispatcher.claim_next_task(db, owner="second", config=config)
            assert first is not None and first.stage_key == "graph"
            assert second is not None and second.stage_key == "profile"
    finally:
        await _cleanup(task_type)


@pytest.mark.asyncio
async def test_pause_and_expired_lease_recovery_are_durable() -> None:
    task_type = f"test_dispatch_recovery_{uuid4().hex}"
    task_worker.register_task_handler(task_type, task_worker._echo_handler)
    config = task_dispatcher.DispatcherConfig(
        max_executors=2,
        lane_limits={"general": 2},
        paused_task_types=frozenset({task_type}),
        allowed_task_types=frozenset({task_type}),
    )
    try:
        async with AsyncSessionLocal() as db:
            task = await task_dispatcher.publish_task(
                db, task_type=task_type, module="test", owner_id=None,
                body={"marker": task_type}, requested_by="test", trigger="pytest",
            )
            task_id = int(task.id)
            await db.commit()
            assert await task_dispatcher.claim_next_task(db, owner="paused", config=config) is None

        active_config = task_dispatcher.DispatcherConfig(
            max_executors=2,
            lane_limits={"general": 2},
            allowed_task_types=frozenset({task_type}),
        )
        async with AsyncSessionLocal() as db:
            claim = await task_dispatcher.claim_next_task(db, owner="active", config=active_config)
            assert claim is not None
            await db.execute(
                update(SystemTaskQueue)
                .where(SystemTaskQueue.id == task_id)
                .values(
                    status="running",
                    lease_expires_at=task_dispatcher._now() - timedelta(seconds=60),
                )
            )
            await db.commit()
        async with AsyncSessionLocal() as db:
            await task_dispatcher.recover_expired_leases(db)
            recovered = await db.get(SystemTaskQueue, task_id)
            assert recovered is not None
            assert recovered.status == "pending"
            assert recovered.lease_token is None
            assert recovered.retry_count == 1
    finally:
        await _cleanup(task_type)


@pytest.mark.asyncio
async def test_missing_lease_running_task_is_recovered() -> None:
    task_type = f"test_dispatch_missing_lease_{uuid4().hex}"
    task_worker.register_task_handler(task_type, task_worker._echo_handler)
    try:
        async with AsyncSessionLocal() as db:
            task = await task_dispatcher.publish_task(
                db, task_type=task_type, module="test", owner_id=None,
                body={"marker": task_type}, requested_by="test", trigger="pytest",
            )
            task.status = "running"
            task.started_at = task_dispatcher._now()
            task_id = int(task.id)
            await db.commit()

        async with AsyncSessionLocal() as db:
            assert await task_dispatcher.recover_expired_leases(db) == 1
            recovered = await db.get(SystemTaskQueue, task_id)
            assert recovered is not None
            assert recovered.status == "pending"
            assert recovered.lease_token is None
            assert recovered.retry_count == 1
    finally:
        await _cleanup(task_type)


def test_handler_registry_only_owns_execution_not_scheduler() -> None:
    failed, reason = task_worker._result_is_semantic_failure({"status": "failed", "error": "boom"})
    assert failed is True and reason == "boom"
    assert not hasattr(task_worker, "start_worker")
    assert not hasattr(task_worker, "_claim_one_task")


def test_task_process_uses_lightweight_handler_bootstrap() -> None:
    """One-shot executors must not load the complete HTTP router registry."""
    from app import task_worker_main
    from app.services.module_registry import list_capabilities
    from app.services.task_handler_bootstrap import bootstrap_task_handlers

    bootstrap_task_handlers()
    source = inspect.getsource(task_worker_main)
    assert "register_routers" not in source
    assert "bootstrap_task_handlers()" in source
    assert task_worker.has_task_handler("kb_pipeline_stage")
    assert task_worker.has_task_handler("kb_enterprise_import")
    assert task_worker.has_task_handler("agent_execute_slow_tool")
    capabilities = {f"{item['module']}:{item['action']}" for item in list_capabilities(role="admin")}
    assert {"pdf-parser:parse", "memory:save", "agent:spawn_subagent"} <= capabilities


def test_dispatcher_document_filter_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASK_DISPATCHER_ALLOWED_DOCUMENT_IDS", "41, 42, invalid")
    config = task_dispatcher._dispatcher_config()
    assert config.allowed_document_ids == frozenset({41, 42})


def test_dispatcher_stage_timeout_overrides_task_default() -> None:
    task = SystemTaskQueue(
        task_type="kb_pipeline_stage",
        module="knowledge",
        parameters="{}",
        stage_key="graph",
        resource_profile={"timeout_seconds": 1200},
    )
    config = task_dispatcher.DispatcherConfig(
        stage_timeouts_seconds={"kb_pipeline_stage": {"graph": 3600}},
    )
    assert task_dispatcher._task_timeout_seconds(task, config) == 3600
