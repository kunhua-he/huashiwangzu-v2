"""Entity graph extraction stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

import logging

from ...models import KbDocument
from ..entity_service import process_document_entities_from_fusions
from ..semantic_align_service import align_document_entities

logger = logging.getLogger("v2.knowledge.pipeline.graph")


async def run(db: AsyncSession, *, doc: KbDocument, **_: object) -> dict:
    if str(getattr(doc, "graph_status", "pending") or "pending") == "done":
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    result = await process_document_entities_from_fusions(db, int(doc.id), int(doc.owner_id))
    # 抽完实体后就地打齐:文本层字级权威纠 OCR/VLM 错字,变体并入锚点(增量自动)。
    # 打齐是增强,失败不拖垮 graph 主流程。
    try:
        align = await align_document_entities(db, int(doc.id), int(doc.owner_id))
        if align.get("aligned"):
            result["semantic_aligned"] = align["aligned"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %d 语义打齐失败(不影响graph): %s", int(doc.id), exc)
    await db.refresh(doc)
    doc.graph_status = "degraded" if result.get("status") == "degraded" else "done"
    return {"status": doc.graph_status, **result}
