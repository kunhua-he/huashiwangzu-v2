"""Page fusion stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..fusion_service import fuse_all_pages


async def run(db: AsyncSession, *, doc: KbDocument, ready_for_fusion, force_fusion: bool = False, **_: object) -> dict:
    if str(getattr(doc, "fusion_status", "pending") or "pending") == "done" and not force_fusion:
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    if not await ready_for_fusion(db, doc):
        return {"document_id": int(doc.id), "status": "blocked", "reason": "upstream_not_ready"}
    return await fuse_all_pages(db, int(doc.id), int(doc.owner_id))
