"""Knowledge source-file lifecycle debt governance."""

from typing import Any, Literal

from app.core.exceptions import ValidationError
from app.models.file import File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import KbDocument
from .document_service import mark_document_source_unavailable
from .source_file_state import classify_file_availability

LifecycleReason = Literal[
    "source_file_deleted",
    "source_file_missing",
    "source_storage_path_missing",
    "source_path_unsafe",
    "source_file_physical_missing",
    "source_unavailable",
]
CONFIRM_ARCHIVE_SOURCE_UNAVAILABLE = "ARCHIVE_SOURCE_UNAVAILABLE"
SOURCE_UNAVAILABLE_REASONS = {
    "source_file_deleted",
    "source_file_missing",
    "source_storage_path_missing",
    "source_path_unsafe",
    "source_file_physical_missing",
}
VALID_LIFECYCLE_REASONS = {*SOURCE_UNAVAILABLE_REASONS, "source_unavailable"}


def _classify_source(file: File | None) -> str:
    state = classify_file_availability(file)
    return "source_available" if state.available else state.reason


def _reason_matches(reason: str, filter_reason: str | None) -> bool:
    if not filter_reason or filter_reason == "source_unavailable":
        return reason in SOURCE_UNAVAILABLE_REASONS
    return reason == filter_reason


def _validate_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    if reason not in VALID_LIFECYCLE_REASONS:
        raise ValidationError(
            "reason must be one of source_file_deleted, source_file_missing, "
            "source_storage_path_missing, source_path_unsafe, "
            "source_file_physical_missing, or source_unavailable"
        )
    return reason


async def _source_unavailable_rows(
    db: AsyncSession,
    owner_id: int | None,
    *,
    reason: str | None = None,
) -> list[tuple[KbDocument, File | None, str]]:
    reason = _validate_reason(reason)
    filters = [KbDocument.deleted.is_(False)]
    if owner_id is not None:
        filters.append(KbDocument.owner_id == owner_id)
    result = await db.execute(
        select(KbDocument, File)
        .outerjoin(File, File.id == KbDocument.file_id)
        .where(*filters)
        .order_by(KbDocument.id.desc())
    )
    rows: list[tuple[KbDocument, File | None, str]] = []
    for doc, file in result.all():
        source_reason = _classify_source(file)
        if not _reason_matches(source_reason, reason):
            continue
        rows.append((doc, file, source_reason))
    return rows


def _item_payload(doc: KbDocument, file: File | None, reason: str) -> dict[str, Any]:
    source_state = classify_file_availability(file)
    return {
        "document_id": int(doc.id),
        "owner_id": int(doc.owner_id),
        "file_id": int(doc.file_id),
        "filename": doc.filename,
        "reason": reason,
        "source_lifecycle_state": _source_lifecycle_state(reason),
        "storage_path": source_state.storage_path,
        "physical_path": source_state.physical_path,
        "parse_error": doc.parse_error,
        "stage_statuses": {
            "parse": doc.parse_status,
            "vector": doc.vector_status,
            "raw": doc.raw_status,
            "fusion": doc.fusion_status,
            "profile": getattr(doc, "profile_status", "pending"),
            "graph": getattr(doc, "graph_status", "pending"),
            "relation": getattr(doc, "relation_status", "pending"),
        },
        "source_file_deleted": bool(file.deleted) if file is not None else None,
        "suggested_action": "archive_source_unavailable_document",
    }


def _source_lifecycle_state(reason: str) -> str:
    if reason == "source_file_deleted":
        return "source_recycled"
    if reason == "source_file_missing":
        return "source_db_missing"
    if reason == "source_file_physical_missing":
        return "source_disk_missing"
    if reason in {"source_storage_path_missing", "source_path_unsafe"}:
        return "source_path_invalid"
    return "source_missing"


async def audit_lifecycle_debt(
    db: AsyncSession,
    owner_id: int | None,
    *,
    limit: int = 500,
    reason: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 500), 5000))
    rows = await _source_unavailable_rows(db, owner_id, reason=reason)
    summary = {reason: 0 for reason in SOURCE_UNAVAILABLE_REASONS}
    items = []
    for doc, file, source_reason in rows:
        summary[source_reason] += 1
        if len(items) < limit:
            items.append(_item_payload(doc, file, source_reason))
    return {
        "dry_run": True,
        "matched": sum(summary.values()),
        "summary": summary,
        "source_recycled_count": summary["source_file_deleted"],
        "source_missing_count": summary["source_file_missing"],
        "source_physical_missing_count": summary["source_file_physical_missing"],
        "candidate_document_ids": [item["document_id"] for item in items],
        "sample_documents": items[:20],
        "items": items,
        "limit": limit,
        "recommended_action": "archive_source_unavailable_documents",
        "owner_scope": "all" if owner_id is None else "current_user",
    }


async def archive_source_unavailable_documents(
    db: AsyncSession,
    owner_id: int | None,
    *,
    dry_run: bool = True,
    limit: int = 100,
    reason: str | None = None,
    confirm: str = "",
    audit_reason: str = "",
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 100), 5000))
    rows = await _source_unavailable_rows(db, owner_id, reason=reason)
    summary = {reason: 0 for reason in SOURCE_UNAVAILABLE_REASONS}
    selected = []
    for doc, file, source_reason in rows:
        summary[source_reason] += 1
        if len(selected) < limit:
            selected.append((doc, file, source_reason))

    items = [_item_payload(doc, file, source_reason) for doc, file, source_reason in selected]
    if dry_run:
        return {
            "dry_run": True,
            "action": "archive_source_unavailable_documents",
            "matched": sum(summary.values()),
            "selected": len(items),
            "changed": 0,
            "summary": summary,
            "changed_by_reason": {reason: 0 for reason in SOURCE_UNAVAILABLE_REASONS},
            "candidate_document_ids": [item["document_id"] for item in items],
            "sample_documents": items[:20],
            "requires_confirm": True,
            "confirm_token": CONFIRM_ARCHIVE_SOURCE_UNAVAILABLE,
            "reason": audit_reason,
            "owner_scope": "all" if owner_id is None else "current_user",
        }

    if confirm != CONFIRM_ARCHIVE_SOURCE_UNAVAILABLE:
        raise ValidationError("confirm must be ARCHIVE_SOURCE_UNAVAILABLE to archive lifecycle debt")

    changed_by_reason = {reason: 0 for reason in SOURCE_UNAVAILABLE_REASONS}
    changed_items = []
    for doc, file, source_reason in selected:
        mark_document_source_unavailable(doc, source_reason)
        doc.deleted = True
        changed_by_reason[source_reason] += 1
        changed_items.append(_item_payload(doc, file, source_reason))
    await db.commit()
    return {
        "dry_run": False,
        "action": "archive_source_unavailable_documents",
        "matched": sum(summary.values()),
        "selected": len(selected),
        "changed": len(changed_items),
        "summary": summary,
        "changed_by_reason": changed_by_reason,
        "changed_items": changed_items,
        "skipped": 0,
        "skipped_items": [],
        "reason": audit_reason,
        "owner_scope": "all" if owner_id is None else "current_user",
    }
