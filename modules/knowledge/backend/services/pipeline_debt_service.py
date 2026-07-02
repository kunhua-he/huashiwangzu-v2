"""Dry-run classification for historical knowledge pipeline queue debt."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.models.file import File
from app.models.system import SystemTaskQueue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KbDocument

FILE_NOT_FOUND_MARKER = "File not found"


def _load_task_parameters(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _classify_task(doc: KbDocument | None, file: File | None) -> tuple[str, str, str | None]:
    if doc is None:
        return "doc_missing", "obsolete", None
    if doc.deleted:
        return "doc_deleted", "obsolete", None
    if file is None:
        return "source_file_missing", "lifecycle_skip", "source_file_missing"
    if file.deleted:
        return "source_file_deleted", "lifecycle_skip", "source_file_deleted"
    return "file_row_live", "retry_or_parser_investigation", None


async def classify_pipeline_lifecycle_debt(
    db: AsyncSession,
    *,
    limit: int = 500,
    error_marker: str = FILE_NOT_FOUND_MARKER,
) -> dict:
    """Classify kb_pipeline File-not-found debt without mutating queue rows."""
    result = await db.execute(
        select(SystemTaskQueue)
        .where(
            SystemTaskQueue.module == "knowledge",
            SystemTaskQueue.task_type == "kb_pipeline",
            SystemTaskQueue.status == "failed",
            SystemTaskQueue.error_message.ilike(f"%{error_marker}%"),
        )
        .order_by(SystemTaskQueue.id.desc())
        .limit(limit)
    )
    tasks = list(result.scalars().all())
    items: list[dict[str, Any]] = []
    summary: Counter[str] = Counter()

    for task in tasks:
        params = _load_task_parameters(task.parameters)
        document_id = int(params.get("document_id", 0) or 0)
        doc = await db.get(KbDocument, document_id) if document_id > 0 else None
        file = await db.get(File, doc.file_id) if doc is not None else None
        category, suggested_action, parse_error = _classify_task(doc, file)
        summary[category] += 1
        item = {
            "task_id": task.id,
            "document_id": document_id or None,
            "file_id": doc.file_id if doc is not None else None,
            "category": category,
            "suggested_action": suggested_action,
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
