"""Shared helpers used by thin stage-node entry points."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..raw_collection_service import collect_raw_stage


async def run_raw_collection_stage(
    db: AsyncSession,
    *,
    doc: KbDocument,
    user_id: int,
    stage: str,
    **_: object,
) -> dict:
    result = await collect_raw_stage(db, int(doc.id), int(doc.owner_id), int(doc.file_id), int(user_id), stage)
    if result.get("raw_complete") and str(getattr(doc, "raw_status", "pending") or "pending") == "collecting":
        doc.raw_status = "done"
    return result
