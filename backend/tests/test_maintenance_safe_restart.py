import json
from uuid import uuid4

import pytest
from app.database import AsyncSessionLocal
from app.main import app
from app.models.system import Setting, SystemTaskQueue
from app.models.user import User
from app.services import task_dispatcher, task_worker
from app.services.auth import create_access_token
from app.services.maintenance_service import (
    MAINTENANCE_SETTING_KEY,
    clear_restart_signal,
    ensure_accepting_new_work,
    get_maintenance_state,
    mark_startup_complete_if_needed,
    request_safe_restart,
    restart_signal_path,
    save_maintenance_state,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select


async def _user(username: str = "admin") -> User:
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == username))
        assert user is not None
        return user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role, user.session_version)
    return {"Authorization": f"Bearer {token}"}


async def _cleanup(marker: str = "") -> None:
    clear_restart_signal()
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Setting).where(Setting.key == MAINTENANCE_SETTING_KEY))
        if marker:
            await db.execute(
                delete(SystemTaskQueue).where(
                    SystemTaskQueue.parameters.like(f"%{marker}%")
                )
            )
        await db.commit()


@pytest.mark.asyncio
async def test_safe_restart_request_enters_draining_and_running_task_blocks_restart() -> None:
    marker = uuid4().hex
    admin = await _user("admin")
    await _cleanup(marker)
    try:
        async with AsyncSessionLocal() as db:
            task = SystemTaskQueue(
                task_type=f"test_maintenance_{marker}",
                module="test",
                parameters=json.dumps({"marker": marker}),
                status="running",
                creator_id=admin.id,
            )
            db.add(task)
            await db.commit()

            result = await request_safe_restart(db, requested_by=admin.id, reason="test")

        assert result["state"]["status"] == "draining"
        assert result["state"]["restart_requested"] is True
        assert result["blockers"]["running_tasks"] >= 1
        assert restart_signal_path().exists()
    finally:
        await _cleanup(marker)


@pytest.mark.asyncio
async def test_draining_queues_new_task_submit_but_blocks_upload_session() -> None:
    marker = uuid4().hex
    admin = await _user("admin")
    await _cleanup(marker)
    try:
        async with AsyncSessionLocal() as db:
            await save_maintenance_state(
                db,
                {
                    "status": "draining",
                    "restart_requested": True,
                    "reason": marker,
                    "requested_by": admin.id,
                },
            )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = _headers(admin)
            task_resp = await client.post(
                "/api/tasks/submit",
                json={
                    "module": "test",
                    "task_type": "_echo",
                    "parameters": {"marker": marker},
                },
                headers=headers,
            )
            upload_resp = await client.post(
                "/api/files/upload-sessions",
                json={"filename": f"maintenance-{marker}.txt", "total_chunks": 1},
                headers=headers,
            )

        assert task_resp.status_code == 200
        assert task_resp.json()["success"] is True
        assert task_resp.json()["data"]["status"] == "pending"
        assert upload_resp.status_code == 503
        assert upload_resp.json()["success"] is False

        async with AsyncSessionLocal() as db:
            with pytest.raises(Exception, match="System maintenance"):
                await ensure_accepting_new_work(db, "test work")
    finally:
        await _cleanup(marker)


@pytest.mark.asyncio
async def test_startup_complete_recovers_restarting_to_normal() -> None:
    admin = await _user("admin")
    await _cleanup()
    try:
        restart_signal_path().parent.mkdir(parents=True, exist_ok=True)
        restart_signal_path().write_text("test", encoding="utf-8")
        async with AsyncSessionLocal() as db:
            await save_maintenance_state(
                db,
                {
                    "status": "restarting",
                    "restart_requested": True,
                    "reason": "test",
                    "requested_by": admin.id,
                },
            )
            await mark_startup_complete_if_needed(db)
            state = await get_maintenance_state(db)

        assert state["status"] == "normal"
        assert state["restart_requested"] is False
        assert not restart_signal_path().exists()
    finally:
        await _cleanup()


@pytest.mark.asyncio
async def test_dispatcher_does_not_claim_pending_task_while_draining() -> None:
    marker = uuid4().hex
    admin = await _user("admin")
    await _cleanup(marker)
    try:
        async with AsyncSessionLocal() as db:
            await save_maintenance_state(
                db,
                {
                    "status": "draining",
                    "restart_requested": True,
                    "reason": marker,
                    "requested_by": admin.id,
                },
            )
            task = SystemTaskQueue(
                task_type=f"test_maintenance_claim_{marker}",
                module="test",
                parameters=json.dumps({"marker": marker}),
                status="pending",
                creator_id=admin.id,
            )
            db.add(task)
            await db.commit()

            task_worker.register_task_handler(task.task_type, task_worker._echo_handler)
            claimed = await task_dispatcher.claim_next_task(
                db,
                owner="maintenance-test",
                config=task_dispatcher.DispatcherConfig(max_executors=1, lane_limits={"general": 1}),
            )
            await db.refresh(task)

        assert claimed is None
        assert task.status == "pending"
    finally:
        await _cleanup(marker)
