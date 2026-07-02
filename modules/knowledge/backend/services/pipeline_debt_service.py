"""Classification and guarded remediation for historical knowledge pipeline debt."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.models.file import File
from app.models.system import SystemTaskQueue
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KbDocument
from .document_service import mark_document_source_unavailable

FILE_NOT_FOUND_MARKER = "File not found"
DOC_NOT_FOUND_PATTERN = "Document % not found"
PARSER_EMPTY_MARKER = "Parser returned no content blocks"
LIFECYCLE_ARCHIVE_CATEGORIES = {
    "doc_missing",
    "doc_deleted",
    "source_file_missing",
    "source_file_deleted",
}
RETRYABLE_CATEGORIES = {"file_row_live"}


def _load_task_parameters(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _classify_task(
    doc: KbDocument | None,
    file: File | None,
    error_message: str | None,
) -> tuple[str, str, str | None]:
    if doc is None:
        return "doc_missing", "archive_obsolete", None
    if doc.deleted:
        return "doc_deleted", "archive_obsolete", None
    if file is None:
        return "source_file_missing", "archive_lifecycle_skip", "source_file_missing"
    if file.deleted:
        return "source_file_deleted", "archive_lifecycle_skip", "source_file_deleted"
    if PARSER_EMPTY_MARKER.lower() in (error_message or "").lower():
        return "parser_no_content_blocks", "parser_quality_investigation", None
    return "file_row_live", "retry_or_parser_investigation", None


def _is_archiveable(category: str) -> bool:
    return category in LIFECYCLE_ARCHIVE_CATEGORIES


def _is_retryable(category: str) -> bool:
    return category in RETRYABLE_CATEGORIES


def _build_error_filter(error_marker: str | None):
    if error_marker:
        return SystemTaskQueue.error_message.ilike(f"%{error_marker}%")
    return or_(
        SystemTaskQueue.error_message.ilike(f"%{FILE_NOT_FOUND_MARKER}%"),
        SystemTaskQueue.error_message.ilike(DOC_NOT_FOUND_PATTERN),
        SystemTaskQueue.error_message.ilike(f"%{PARSER_EMPTY_MARKER}%"),
    )


async def _load_candidate_tasks(
    db: AsyncSession,
    *,
    limit: int = 500,
    error_marker: str | None = None,
    task_ids: list[int] | None = None,
) -> list[SystemTaskQueue]:
    error_filter = _build_error_filter(error_marker)
    filters = [
        SystemTaskQueue.module == "knowledge",
        SystemTaskQueue.task_type == "kb_pipeline",
        SystemTaskQueue.status == "failed",
        error_filter,
    ]
    if task_ids:
        filters.append(SystemTaskQueue.id.in_(task_ids))
    result = await db.execute(
        select(SystemTaskQueue)
        .where(*filters)
        .order_by(SystemTaskQueue.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _classify_tasks(db: AsyncSession, tasks: list[SystemTaskQueue]) -> dict:
    items: list[dict[str, Any]] = []
    summary: Counter[str] = Counter()

    for task in tasks:
        params = _load_task_parameters(task.parameters)
        document_id = int(params.get("document_id", 0) or 0)
        doc = await db.get(KbDocument, document_id) if document_id > 0 else None
        file = await db.get(File, doc.file_id) if doc is not None else None
        category, suggested_action, parse_error = _classify_task(doc, file, task.error_message)
        summary[category] += 1
        item = {
            "task_id": task.id,
            "document_id": document_id or None,
            "file_id": doc.file_id if doc is not None else None,
            "category": category,
            "suggested_action": suggested_action,
            "archiveable": _is_archiveable(category),
            "retryable": _is_retryable(category),
            "would_set_parse_error": parse_error,
            "queue_status": task.status,
            "error_message": task.error_message,
        }
        items.append(item)

    return {
        "dry_run": True,
        "matched": len(items),
        "summary": dict(summary),
        "items": items,
    }


async def classify_pipeline_lifecycle_debt(
    db: AsyncSession,
    *,
    limit: int = 500,
    error_marker: str | None = None,
    task_ids: list[int] | None = None,
) -> dict:
    """Classify kb_pipeline debt without mutating queue rows."""
    tasks = await _load_candidate_tasks(
        db,
        limit=limit,
        error_marker=error_marker,
        task_ids=task_ids,
    )
    return await _classify_tasks(db, tasks)


def _archive_task(task: SystemTaskQueue, item: dict[str, Any], now: datetime) -> None:
    previous_error = task.error_message
    task.status = "completed"
    task.completed_at = now
    task.started_at = None
    task.error_message = None
    task.result = json.dumps({
        "status": "skipped",
        "archived_by": "knowledge_pipeline_debt_governance",
        "classification": item["category"],
        "reason": item["would_set_parse_error"] or item["category"],
        "document_id": item["document_id"],
        "file_id": item["file_id"],
        "previous_error_message": previous_error,
    }, ensure_ascii=False)


def _retry_task(task: SystemTaskQueue, item: dict[str, Any]) -> None:
    previous_error = task.error_message
    task.status = "pending"
    task.retry_count = 0
    task.started_at = None
    task.completed_at = None
    task.error_message = None
    task.result = json.dumps({
        "status": "requeued",
        "requeued_by": "knowledge_pipeline_debt_governance",
        "classification": item["category"],
        "document_id": item["document_id"],
        "file_id": item["file_id"],
        "previous_error_message": previous_error,
    }, ensure_ascii=False)


async def _mark_document_for_archived_lifecycle_debt(
    db: AsyncSession,
    item: dict[str, Any],
) -> None:
    reason = item.get("would_set_parse_error")
    document_id = int(item.get("document_id") or 0)
    if not reason or document_id <= 0:
        return
    doc = await db.get(KbDocument, document_id)
    if doc is None or doc.deleted:
        return
    mark_document_source_unavailable(doc, str(reason))


async def apply_pipeline_lifecycle_debt_action(
    db: AsyncSession,
    *,
    action: str,
    limit: int = 500,
    task_ids: list[int] | None = None,
    dry_run: bool = True,
) -> dict:
    """Apply a guarded governance action to classified historical debt.

    ``archive_obsolete`` only converts lifecycle-obsolete rows to completed
    skipped results. ``retry_live`` only requeues rows whose framework file row
    is still live. Parser quality debt is intentionally never auto-mutated.
    """
    if action not in {"archive_obsolete", "retry_live"}:
        raise ValueError("Unsupported pipeline debt action")

    tasks = await _load_candidate_tasks(db, limit=limit, task_ids=task_ids)
    classification = await _classify_tasks(db, tasks)
    tasks_by_id = {int(task.id): task for task in tasks}
    changed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for item in classification["items"]:
        task = tasks_by_id.get(int(item["task_id"]))
        if task is None:
            continue
        if action == "archive_obsolete" and item["archiveable"]:
            changed.append(item)
            if not dry_run:
                await _mark_document_for_archived_lifecycle_debt(db, item)
                _archive_task(task, item, now)
        elif action == "retry_live" and item["retryable"]:
            changed.append(item)
            if not dry_run:
                _retry_task(task, item)
        else:
            skipped.append({
                **item,
                "skip_reason": "action_not_allowed_for_category",
            })

    if not dry_run and changed:
        await db.commit()

    return {
        "dry_run": dry_run,
        "action": action,
        "matched": classification["matched"],
        "changed": len(changed),
        "skipped": len(skipped),
        "summary": classification["summary"],
        "changed_items": changed,
        "skipped_items": skipped,
    }
