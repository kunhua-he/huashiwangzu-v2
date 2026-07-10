"""Automatic reconciliation for incomplete knowledge pipeline documents."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.database import AsyncSessionLocal
from app.models.file import File
from app.models.system import SystemTaskQueue
from app.services.task_worker import register_task_handler
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KbDocument
from .document_service import KNOWLEDGE_PIPELINE_MAX_RETRIES, enqueue_incomplete_documents

logger = logging.getLogger("v2.knowledge").getChild("pipeline_autofill")

PIPELINE_AUTOFILL_TASK_TYPE = "kb_pipeline_autofill"
PIPELINE_AUTOFILL_LOCK_KEY = 1262633051
PIPELINE_AUTOFILL_RECUR = "hourly"
SPECIAL_FAILURE_MARKERS = (
    "model_refusal",
    "model refused",
    "refused to",
    "safety policy",
    "content policy",
)


def _is_special_failure(error_message: str | None) -> bool:
    lowered = (error_message or "").lower()
    return any(marker in lowered for marker in SPECIAL_FAILURE_MARKERS)


async def ensure_pipeline_autofill_task(db: AsyncSession) -> dict[str, Any]:
    """Ensure one recurring autofill task exists so gaps are repaired without UI help."""
    acquired = await db.scalar(text("SELECT pg_try_advisory_xact_lock(:lock_key)"), {"lock_key": PIPELINE_AUTOFILL_LOCK_KEY})
    if not acquired:
        return {"ensured": False, "reason": "lock_busy"}

    result = await db.execute(
        select(SystemTaskQueue)
        .where(
            SystemTaskQueue.module == "knowledge",
            SystemTaskQueue.task_type == PIPELINE_AUTOFILL_TASK_TYPE,
            SystemTaskQueue.status.in_(("pending", "running")),
        )
        .order_by(SystemTaskQueue.id.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return {"ensured": True, "created": False, "task_id": int(existing.id)}

    task = SystemTaskQueue(
        task_type=PIPELINE_AUTOFILL_TASK_TYPE,
        module="knowledge",
        parameters=json.dumps({"limit_per_owner": 500, "failed_retry_limit": 200}, ensure_ascii=False),
        status="pending",
        priority=1,
        max_retries=KNOWLEDGE_PIPELINE_MAX_RETRIES,
        recur=PIPELINE_AUTOFILL_RECUR,
        next_run_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()
    await db.commit()
    return {"ensured": True, "created": True, "task_id": int(task.id)}


async def _requeue_retryable_failed_tasks(db: AsyncSession, *, limit: int) -> dict[str, Any]:
    active_result = await db.execute(
        select(SystemTaskQueue.document_id, SystemTaskQueue.stage_key)
        .where(
            SystemTaskQueue.module == "knowledge",
            SystemTaskQueue.task_type == "kb_pipeline_stage",
            SystemTaskQueue.status.in_(("pending", "running")),
            SystemTaskQueue.document_id.is_not(None),
        )
    )
    active_doc_stages = {
        (int(document_id), str(stage_key or ""))
        for document_id, stage_key in active_result.all()
        if document_id is not None
    }

    result = await db.execute(
        select(SystemTaskQueue)
        .join(KbDocument, KbDocument.id == SystemTaskQueue.document_id)
        .join(File, File.id == KbDocument.file_id)
        .where(
            SystemTaskQueue.module == "knowledge",
            SystemTaskQueue.task_type == "kb_pipeline_stage",
            SystemTaskQueue.status == "failed",
            SystemTaskQueue.document_id.is_not(None),
            SystemTaskQueue.retry_count < KNOWLEDGE_PIPELINE_MAX_RETRIES,
            KbDocument.deleted.is_(False),
            File.deleted.is_(False),
        )
        .order_by(SystemTaskQueue.completed_at.asc().nulls_first(), SystemTaskQueue.id.asc())
        .limit(max(1, min(int(limit or 200), 1000)))
    )
    requeued = 0
    skipped_special = 0
    skipped_active = 0
    for task in result.scalars().all():
        if _is_special_failure(task.error_message):
            skipped_special += 1
            continue
        doc_stage = (int(task.document_id or 0), str(task.stage_key or ""))
        if doc_stage in active_doc_stages:
            skipped_active += 1
            continue
        previous_error = task.error_message
        task.status = "pending"
        task.max_retries = max(int(task.max_retries or 0), KNOWLEDGE_PIPELINE_MAX_RETRIES)
        task.started_at = None
        task.completed_at = None
        task.error_message = None
        task.result = json.dumps({
            "status": "requeued",
            "requeued_by": PIPELINE_AUTOFILL_TASK_TYPE,
            "previous_error_message": previous_error,
            "retry_count_preserved": int(task.retry_count or 0),
        }, ensure_ascii=False)
        requeued += 1
        active_doc_stages.add(doc_stage)
    return {
        "requeued_failed_tasks": requeued,
        "skipped_special_failures": skipped_special,
        "skipped_active_doc_stages": skipped_active,
    }


async def _owner_ids_with_incomplete_documents(db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(KbDocument.owner_id)
        .join(File, File.id == KbDocument.file_id)
        .where(
            KbDocument.deleted.is_(False),
            File.deleted.is_(False),
            or_(
                KbDocument.parse_status.not_in(("done", "degraded")),
                KbDocument.vector_status != "done",
                KbDocument.raw_status != "done",
                KbDocument.fusion_status != "done",
                KbDocument.profile_status != "done",
                KbDocument.graph_status != "done",
                KbDocument.relation_status != "done",
            ),
        )
        .distinct()
    )
    return [int(owner_id) for owner_id in result.scalars().all() if owner_id is not None]


async def pipeline_autofill_once(
    db: AsyncSession,
    *,
    limit_per_owner: int = 500,
    failed_retry_limit: int = 200,
) -> dict[str, Any]:
    retry_result = await _requeue_retryable_failed_tasks(db, limit=failed_retry_limit)
    owner_ids = await _owner_ids_with_incomplete_documents(db)
    owner_results: list[dict[str, Any]] = []
    total_enqueued = 0
    total_inflight = 0
    for owner_id in owner_ids:
        result = await enqueue_incomplete_documents(
            db,
            owner_id=owner_id,
            limit=limit_per_owner,
            dry_run=False,
            priority=8,
            include_search_incomplete=True,
        )
        total_enqueued += int(result.get("enqueued") or 0)
        total_inflight += int(result.get("already_in_flight") or 0)
        owner_results.append({
            "owner_id": owner_id,
            "matched": int(result.get("matched") or 0),
            "enqueued": int(result.get("enqueued") or 0),
            "already_in_flight": int(result.get("already_in_flight") or 0),
            "scanned": int(result.get("scanned") or 0),
        })
    await db.commit()
    return {
        "status": "done",
        **retry_result,
        "owners": owner_results,
        "owner_count": len(owner_results),
        "enqueued_incomplete_documents": total_enqueued,
        "already_in_flight_documents": total_inflight,
    }


async def _pipeline_autofill_handler(params: dict) -> dict:
    limit_per_owner = int(params.get("limit_per_owner") or 500)
    failed_retry_limit = int(params.get("failed_retry_limit") or 200)
    async with AsyncSessionLocal() as db:
        return await pipeline_autofill_once(
            db,
            limit_per_owner=limit_per_owner,
            failed_retry_limit=failed_retry_limit,
        )


register_task_handler(PIPELINE_AUTOFILL_TASK_TYPE, _pipeline_autofill_handler)
