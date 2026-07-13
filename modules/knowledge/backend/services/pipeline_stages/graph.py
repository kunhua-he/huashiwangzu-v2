"""Entity graph extraction stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..entity_service import process_document_entities_from_fusions


async def run(db: AsyncSession, *, doc: KbDocument, **_: object) -> dict:
    if str(getattr(doc, "graph_status", "pending") or "pending") == "done":
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    result = await process_document_entities_from_fusions(db, int(doc.id), int(doc.owner_id))
    await db.refresh(doc)
    doc.graph_status = "degraded" if result.get("status") == "degraded" else "done"
    return {"status": doc.graph_status, **result}
