"""Cross-document relation build stage."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..节点08_跨文档串联 import 跨文档串联


async def run(db: AsyncSession, *, doc: KbDocument, **_: object) -> dict:
    if str(getattr(doc, "relation_status", "pending") or "pending") == "done":
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    # 节点⑧:跨文档归并 + 主体关系 + 相似边门禁(替换原 compute_file_relations 直调)
    result = await 跨文档串联(db, int(doc.id), int(doc.owner_id))
    await db.refresh(doc)
    doc.relation_status = "done"
    return {"status": "done", **result}
