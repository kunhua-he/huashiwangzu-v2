"""Source availability validation stage."""
from __future__ import annotations

from app.services.file_service import check_file_access
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..document_service import (
    SOURCE_UNAVAILABLE_REASONS,
    mark_document_non_content_skipped,
    mark_document_source_unavailable,
)
from ..source_file_state import classify_non_content_file, get_source_file_availability


async def run(db: AsyncSession, *, doc: KbDocument, **_: object) -> dict:
    await check_file_access(db, int(doc.file_id), int(doc.owner_id))
    source_state = await get_source_file_availability(db, int(doc.file_id))
    if not source_state.available:
        mark_document_source_unavailable(doc, source_state.reason)
        await db.commit()
        return {"document_id": int(doc.id), "status": "skipped", "reason": source_state.reason}
    if (doc.parse_error or "") in SOURCE_UNAVAILABLE_REASONS:
        doc.parse_error = None
    non_content_reason = classify_non_content_file(doc, source_state.physical_path)
    if non_content_reason:
        mark_document_non_content_skipped(doc, non_content_reason)
        await db.commit()
        return {"document_id": int(doc.id), "file_id": int(doc.file_id), "status": "skipped", "reason": non_content_reason}
    return {"document_id": int(doc.id), "status": "done", "reason": "source_available"}
