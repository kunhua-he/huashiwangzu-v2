"""Derived cognitive index stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..cognitive_index_service import derive_document_cognitive_index
from ..model_routing import resolve_knowledge_concurrency


async def run(db: AsyncSession, *, doc: KbDocument, cognitive_index_complete, ready_for_cognitive_index, **_: object) -> dict:
    if await cognitive_index_complete(db, doc):
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    if not ready_for_cognitive_index(doc):
        return {"document_id": int(doc.id), "status": "blocked", "reason": "upstream_not_ready"}
    limit = resolve_knowledge_concurrency("cognitive_terms_per_document", 200, minimum=20, maximum=1000)
    result = await derive_document_cognitive_index(
        db,
        owner_id=int(doc.owner_id),
        document_id=int(doc.id),
        limit=limit,
    )
    return {"status": "done", "document_id": int(doc.id), "limit": limit, **result}
