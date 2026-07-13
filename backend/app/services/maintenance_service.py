"""Platform maintenance and safe-restart gate."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, ValidationError
from app.models.file_upload_session import FileUploadSession
from app.models.system import Setting, SystemTaskQueue

MAINTENANCE_SETTING_KEY = "platform.maintenance"
VALID_STATUSES = {"normal", "draining", "restarting", "failed"}
BLOCKING_UPLOAD_STATUSES = {"pending", "uploading", "uploaded"}
ACTIVE_UPLOAD_WINDOW_SECONDS = 30 * 60
RESTARTABLE_BACKGROUND_MODULES = frozenset({"knowledge"})


def restart_signal_path() -> Path:
    return Path(__file__).resolve().parents[2] / "logs" / ".safe_restart_requested"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict[str, Any]:
    return {
        "status": "normal",
        "restart_requested": False,
        "reason": "",
        "requested_by": None,
        "requested_at": None,
        "updated_at": _now_iso(),
        "last_error": None,
    }


def _parse_state(value: str | None) -> dict[str, Any]:
    if not value:
        return _default_state()
    try:
        state = json.loads(value)
    except json.JSONDecodeError:
        state = _default_state()
        state["status"] = "failed"
        state["last_error"] = "maintenance state JSON is invalid"
        return state
    if not isinstance(state, dict):
        return _default_state()
    merged = {**_default_state(), **state}
    if merged.get("status") not in VALID_STATUSES:
        merged["status"] = "failed"
        merged["last_error"] = "maintenance state status is invalid"
    return merged


async def get_maintenance_state(db: AsyncSession) -> dict[str, Any]:
    row = await db.scalar(select(Setting).where(Setting.key == MAINTENANCE_SETTING_KEY))
    return _parse_state(row.value if row else None)


async def save_maintenance_state(db: AsyncSession, state: dict[str, Any]) -> dict[str, Any]:
    status = str(state.get("status") or "normal")
    if status not in VALID_STATUSES:
        raise ValidationError(f"Invalid maintenance status: {status}")
    state = {**_default_state(), **state, "status": status, "updated_at": _now_iso()}
    value = json.dumps(state, ensure_ascii=False, default=str)
    row = await db.scalar(select(Setting).where(Setting.key == MAINTENANCE_SETTING_KEY))
    if row:
        row.value = value
        row.description = "Platform maintenance and safe restart state"
    else:
        db.add(Setting(
            key=MAINTENANCE_SETTING_KEY,
            value=value,
            description="Platform maintenance and safe restart state",
        ))
    await db.commit()
    return state


async def get_restart_blockers(db: AsyncSession) -> dict[str, Any]:
    running_count = int(await db.scalar(
        select(func.count(SystemTaskQueue.id)).where(SystemTaskQueue.status == "running")
    ) or 0)
    running_rows = await db.execute(
        select(
            SystemTaskQueue.id,
            SystemTaskQueue.task_type,
            SystemTaskQueue.module,
            SystemTaskQueue.creator_id,
            SystemTaskQueue.started_at,
        )
        .where(SystemTaskQueue.status == "running")
        .order_by(SystemTaskQueue.started_at.asc().nulls_last(), SystemTaskQueue.id.asc())
        .limit(20)
    )
    running_sample = [
        {
            "id": int(row.id),
            "task_type": row.task_type,
            "module": row.module,
            "creator_id": row.creator_id,
            "started_at": row.started_at,
        }
        for row in running_rows.all()
    ]
    restartable_running_count = int(await db.scalar(
        select(func.count(SystemTaskQueue.id)).where(
            SystemTaskQueue.status == "running",
            SystemTaskQueue.module.in_(RESTARTABLE_BACKGROUND_MODULES),
        )
    ) or 0)
    blocking_running_count = int(await db.scalar(
        select(func.count(SystemTaskQueue.id)).where(
            SystemTaskQueue.status == "running",
            or_(
                SystemTaskQueue.module.is_(None),
                SystemTaskQueue.module.not_in(RESTARTABLE_BACKGROUND_MODULES),
            ),
        )
    ) or 0)
    restartable_task_sample = [
        row for row in running_sample
        if row.get("module") in RESTARTABLE_BACKGROUND_MODULES
    ]
    blocking_task_sample = [
        row for row in running_sample
        if row.get("module") not in RESTARTABLE_BACKGROUND_MODULES
    ]

    active_since = datetime.now(timezone.utc) - timedelta(seconds=ACTIVE_UPLOAD_WINDOW_SECONDS)
    upload_count = int(await db.scalar(
        select(func.count(FileUploadSession.id)).where(
            FileUploadSession.deleted.is_(False),
            FileUploadSession.status.in_(BLOCKING_UPLOAD_STATUSES),
            FileUploadSession.updated_at >= active_since,
        )
    ) or 0)
    upload_rows = await db.execute(
        select(
            FileUploadSession.session_id,
            FileUploadSession.filename,
            FileUploadSession.owner_id,
            FileUploadSession.status,
            FileUploadSession.updated_at,
        )
        .where(
            FileUploadSession.deleted.is_(False),
            FileUploadSession.status.in_(BLOCKING_UPLOAD_STATUSES),
            FileUploadSession.updated_at >= active_since,
        )
        .order_by(FileUploadSession.updated_at.desc())
        .limit(20)
    )
    upload_sample = [
        {
            "session_id": row.session_id,
            "filename": row.filename,
            "owner_id": row.owner_id,
            "status": row.status,
            "updated_at": row.updated_at,
        }
        for row in upload_rows.all()
    ]

    active_user_ids = sorted({
        int(row["creator_id"])
        for row in running_sample
        if row.get("creator_id") is not None
    } | {
        int(row["owner_id"])
        for row in upload_sample
        if row.get("owner_id") is not None
    })
    blocking_active_user_ids = sorted({
        int(row["creator_id"])
        for row in blocking_task_sample
        if row.get("creator_id") is not None
    } | {
        int(row["owner_id"])
        for row in upload_sample
        if row.get("owner_id") is not None
    })
    return {
        "running_tasks": running_count,
        "restartable_running_tasks": restartable_running_count,
        "blocking_running_tasks": blocking_running_count,
        "active_upload_sessions": upload_count,
        "active_user_ids": active_user_ids,
        "blocking_active_user_ids": blocking_active_user_ids,
        "blocking_count": blocking_running_count + upload_count,
        "running_task_sample": running_sample,
        "restartable_task_sample": restartable_task_sample,
        "blocking_task_sample": blocking_task_sample,
        "active_upload_sample": upload_sample,
    }


async def maintenance_snapshot(db: AsyncSession) -> dict[str, Any]:
    state = await get_maintenance_state(db)
    blockers = await get_restart_blockers(db)
    return {"state": state, "blockers": blockers}


def _touch_restart_signal() -> None:
    signal = restart_signal_path()
    signal.parent.mkdir(parents=True, exist_ok=True)
    signal.write_text(_now_iso(), encoding="utf-8")


def clear_restart_signal() -> None:
    restart_signal_path().unlink(missing_ok=True)


async def request_safe_restart(
    db: AsyncSession,
    *,
    requested_by: int | None,
    reason: str = "",
) -> dict[str, Any]:
    state = await get_maintenance_state(db)
    if state.get("status") == "restarting":
        raise AppException("Backend restart is already in progress", status_code=409)
    next_state = {
        **state,
        "status": "draining",
        "restart_requested": True,
        "reason": reason,
        "requested_by": requested_by,
        "requested_at": state.get("requested_at") or _now_iso(),
        "last_error": None,
    }
    saved = await save_maintenance_state(db, next_state)
    _touch_restart_signal()
    return {"state": saved, "blockers": await get_restart_blockers(db)}


async def cancel_safe_restart(db: AsyncSession) -> dict[str, Any]:
    clear_restart_signal()
    state = await save_maintenance_state(db, _default_state())
    return {"state": state, "blockers": await get_restart_blockers(db)}


async def mark_restarting_if_ready(db: AsyncSession) -> dict[str, Any]:
    state = await get_maintenance_state(db)
    blockers = await get_restart_blockers(db)
    if state.get("status") != "draining" or not state.get("restart_requested"):
        return {"ready": False, "state": state, "blockers": blockers}
    if blockers["blocking_count"] > 0:
        return {"ready": False, "state": state, "blockers": blockers}
    saved = await save_maintenance_state(db, {**state, "status": "restarting"})
    return {"ready": True, "state": saved, "blockers": blockers}


async def restart_preflight(db: AsyncSession) -> dict[str, Any]:
    """Check whether a direct backend restart would be safe right now."""
    state = await get_maintenance_state(db)
    blockers = await get_restart_blockers(db)
    return {
        "ready": blockers["blocking_count"] == 0,
        "state": state,
        "blockers": blockers,
    }


async def mark_startup_complete_if_needed(db: AsyncSession) -> None:
    state = await get_maintenance_state(db)
    if state.get("status") == "restarting":
        clear_restart_signal()
        await save_maintenance_state(db, _default_state())


async def ensure_accepting_new_work(db: AsyncSession, work_type: str = "work") -> None:
    state = await get_maintenance_state(db)
    if state.get("status") in {"draining", "restarting"}:
        raise AppException(
            f"System maintenance is {state['status']}; new {work_type} is temporarily disabled",
            code="MAINTENANCE_DRAINING",
            status_code=503,
        )
