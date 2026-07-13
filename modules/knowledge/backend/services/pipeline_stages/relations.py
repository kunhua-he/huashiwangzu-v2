"""Cross-document relation build stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..relation_service import compute_file_relations


async def run(db: AsyncSession, *, doc: KbDocument, **_: object) -> dict:
    if str(getattr(doc, "relation_status", "pending") or "pending") == "done":
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    result = await compute_file_relations(db, int(doc.id), int(doc.owner_id))
    await db.refresh(doc)
    doc.relation_status = "done"
    return {"status": "done", **result}
