"""Document profile stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..profile_service import generate_document_profile


async def run(db: AsyncSession, *, doc: KbDocument, **_: object) -> dict:
    if str(getattr(doc, "profile_status", "pending") or "pending") == "done":
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    result = await generate_document_profile(db, int(doc.id), int(doc.owner_id))
    await db.refresh(doc)
    if result.get("status") == "skipped":
        doc.profile_status = "degraded"
    return result
