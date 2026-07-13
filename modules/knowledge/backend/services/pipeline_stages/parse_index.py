"""Parse and base-index stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..document_service import document_parse_allows_search, document_vector_stage_terminal, parse_and_index_document


async def run(
    db: AsyncSession,
    *,
    doc: KbDocument,
    user_id: int,
    task_id: int | None = None,
    force_raw: bool = False,
    **_: object,
) -> dict:
    if document_parse_allows_search(doc) and document_vector_stage_terminal(doc) and not force_raw:
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    result = await parse_and_index_document(
        db,
        document_id=int(doc.id),
        owner_id=int(doc.owner_id),
        caller=f"user:{user_id}",
        extract_graph=False,
        current_task_id=task_id,
    )
    await db.refresh(doc)
    return {"status": "done" if document_parse_allows_search(doc) else "degraded", **result}
