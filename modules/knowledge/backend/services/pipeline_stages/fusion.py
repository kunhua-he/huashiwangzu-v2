"""Page fusion stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..节点06_单页融合 import fuse_document


async def run(
    db: AsyncSession,
    *,
    doc: KbDocument,
    ready_for_fusion,
    force_fusion: bool = False,
    **_: object,
) -> dict:
    if str(getattr(doc, "fusion_status", "pending") or "pending") == "done" and not force_fusion:
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    if not await ready_for_fusion(db, doc):
        return {"document_id": int(doc.id), "status": "blocked", "reason": "upstream_not_ready"}
    # 节点⑥:文本层优先,LLM 降级为补充/兜底(替换 fuse_all_pages 直调)
    return await fuse_document(db, int(doc.id), int(doc.owner_id), force=bool(force_fusion))
