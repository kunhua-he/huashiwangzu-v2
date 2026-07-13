import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFound, PermissionDenied, ValidationError
from app.database import get_db
from app.middleware.auth import require_permission
from app.models.system import SystemTaskQueue
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.system import SystemTaskQueueResponse, WorkerStatusResponse
from app.services.task_debt_governance_service import DEFAULT_DEBT_GOVERNANCE_LIMIT, govern_task_queue_debt
from app.services.task_dispatcher import publish_task
from app.services.task_queue_audit_service import (
    audit_task_queue,
    reconcile_orphan_running,
    reconcile_stale_pending,
)
from app.services.task_worker import has_task_handler

router = APIRouter(prefix="/api/tasks", tags=["system-tasks"])
logger = logging.getLogger("v2.tasks")


class TaskSubmitRequest(BaseModel):
    module: str
    task_type: str
    parameters: dict | None = None
    priority: int = 0


class TaskDebtGovernanceRequest(BaseModel):
    dry_run: bool = True
    limit: int = DEFAULT_DEBT_GOVERNANCE_LIMIT
    sample_limit: int = 5
    task_ids: list[int] | None = None
    confirm_all_failed: bool = False


def _ensure_task_owner_or_admin(task: SystemTaskQueue, user: User) -> None:
    if user.role != "admin" and task.creator_id != user.id:
        raise PermissionDenied("Permission denied")


def _retry_diagnostics(task: SystemTaskQueue) -> dict:
    """Return only durable, operator-useful state for retry logs."""
    return {
        "task_id": int(task.id),
        "task_type": task.task_type,
        "module": task.module,
        "status": task.status,
        "document_id": task.document_id,
        "stage_key": task.stage_key,
        "lane_key": task.lane_key,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
        "attempt": task.attempt,
        "lease_owner": task.lease_owner,
        "lease_expires_at": task.lease_expires_at.isoformat() if task.lease_expires_at else None,
        "failure_class": task.failure_class,
        "blocked_reason": task.blocked_reason,
    }


async def _find_active_retry_duplicate(
    db: AsyncSession,
    task: SystemTaskQueue,
) -> SystemTaskQueue | None:
    """Find the live DAG task that would violate the active-stage constraint."""
    if task.task_type != "kb_pipeline_stage" or task.document_id is None or not task.stage_key:
        return None
    return await db.scalar(
        select(SystemTaskQueue)
        .where(
            SystemTaskQueue.id != task.id,
            SystemTaskQueue.task_type == task.task_type,
            SystemTaskQueue.document_id == task.document_id,
            SystemTaskQueue.stage_key == task.stage_key,
            SystemTaskQueue.status.in_(("pending", "running")),
        )
        .order_by(desc(SystemTaskQueue.id))
        .limit(1)
    )


@router.get("/")
async def task_list(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    stmt = select(SystemTaskQueue)
    if user.role != "admin":
        stmt = stmt.where(SystemTaskQueue.creator_id == user.id)
    r = await db.execute(
        stmt.order_by(desc(SystemTaskQueue.id)).limit(50)
    )
    items = [SystemTaskQueueResponse.model_validate(i) for i in r.scalars().all()]
    return ApiResponse(data=items)


@router.get("/worker/status")
async def worker_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    r = await db.execute(
        select(SystemTaskQueue.status, func.count(SystemTaskQueue.id))
        .group_by(SystemTaskQueue.status)
    )
    counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
    for row in r.all():
        counts[row[0]] = row[1]
    now = datetime.now(timezone.utc)
    oldest = await db.scalar(
        select(SystemTaskQueue.created_at)
        .where(
            and_(
                SystemTaskQueue.status == "pending",
                or_(
                    SystemTaskQueue.scheduled_at.is_(None),
                    SystemTaskQueue.scheduled_at <= now,
                ),
            )
        )
        .order_by(SystemTaskQueue.created_at).limit(1)
    )
    wait_secs = int((now - oldest).total_seconds()) if oldest else None
    return ApiResponse(data=WorkerStatusResponse(
        pending=counts["pending"], running=counts["running"],
        completed=counts["completed"], failed=counts["failed"],
        oldest_waiting_seconds=wait_secs,
    ))


@router.get("/worker/audit")
async def worker_audit(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    audit = await audit_task_queue(db)
    return ApiResponse(data=audit)


@router.post("/worker/reconcile")
async def worker_reconcile(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    orphans = await reconcile_orphan_running(db)
    stale = await reconcile_stale_pending(db)
    return ApiResponse(data={
        "orphans_reconciled": orphans,
        "stale_pending_reconciled": stale,
    })


@router.post("/worker/governance")
async def worker_debt_governance(
    payload: TaskDebtGovernanceRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    if not payload.dry_run and not payload.task_ids and not payload.confirm_all_failed:
        raise ValidationError("Non-dry-run governance requires task_ids or confirm_all_failed=true")
    result = await govern_task_queue_debt(
        db,
        dry_run=payload.dry_run,
        limit=payload.limit,
        sample_limit=payload.sample_limit,
        task_ids=payload.task_ids,
        confirm_all_failed=payload.confirm_all_failed,
    )
    return ApiResponse(data=result)


@router.get("/{task_id}")
async def task_detail(
    task_id: int, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    task = await db.get(SystemTaskQueue, task_id)
    if not task:
        raise NotFound("Task not found")
    _ensure_task_owner_or_admin(task, user)
    return ApiResponse(data=SystemTaskQueueResponse.model_validate(task))


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: int, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    task = await db.scalar(
        select(SystemTaskQueue)
        .where(SystemTaskQueue.id == task_id)
        .with_for_update()
    )
    if not task:
        raise NotFound("Task not found")
    _ensure_task_owner_or_admin(task, user)
    if task.status != "failed":
        raise ValidationError("Only failed tasks can be retried")
    duplicate = await _find_active_retry_duplicate(db, task)
    if duplicate is not None:
        logger.warning(
            "Task retry conflict: failed task already has an active knowledge stage retry=%s active=%s",
            _retry_diagnostics(task),
            _retry_diagnostics(duplicate),
        )
        raise ConflictError(
            "Retry not queued: an active task already exists for this knowledge document stage "
            f"(task_id={duplicate.id}, status={duplicate.status})"
        )
    task.status = "pending"
    task.retry_count = 0
    task.error_message = None
    task.result = None
    task.started_at = None
    task.completed_at = None
    task.lease_token = None
    task.lease_owner = None
    task.lease_expires_at = None
    task.heartbeat_at = None
    task.retry_at = None
    task.failure_class = None
    task.blocked_reason = None
    task.executor_pid = None
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception(
            "Task retry database failure task=%s error_type=%s error=%s",
            _retry_diagnostics(task),
            type(exc).__name__,
            str(exc),
        )
        raise ConflictError("Retry was not queued because queue state changed; inspect task retry diagnostics and try again") from exc
    logger.info("Task manually re-queued retry=%s", _retry_diagnostics(task))
    return ApiResponse(data={"ok": True, "message": "Task re-queued"})


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: int, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    task = await db.get(SystemTaskQueue, task_id)
    if not task:
        raise NotFound("Task not found")
    _ensure_task_owner_or_admin(task, user)
    if task.status not in ("pending", "running"):
        raise ValidationError("Only pending or running tasks can be cancelled")
    task.status = "failed"
    task.error_message = "Manually cancelled"
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return ApiResponse(data={"ok": True, "message": "Task cancelled"})


@router.post("/submit")
async def submit_task(
    payload: TaskSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    if not has_task_handler(payload.task_type):
        raise ValidationError(f"No handler registered for task_type '{payload.task_type}'")
    task = await publish_task(
        db,
        task_type=payload.task_type,
        module=payload.module,
        owner_id=user.id,
        body=payload.parameters or {},
        requested_by=f"user:{user.id}",
        trigger="api.tasks.submit",
        priority=payload.priority,
    )
    await db.commit()
    await db.refresh(task)
    return ApiResponse(data=SystemTaskQueueResponse.model_validate(task))
