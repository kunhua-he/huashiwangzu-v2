"""Entity graph extraction stage."""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument
from ..节点03_三路交叉纠错 import 纠错回写
from ..节点07_文档级串联 import 串联

logger = logging.getLogger("v2.knowledge.pipeline.graph")


async def run(db: AsyncSession, *, doc: KbDocument, **_: object) -> dict:
    if str(getattr(doc, "graph_status", "pending") or "pending") == "done":
        return {"document_id": int(doc.id), "status": "skipped", "reason": "already done"}
    # 节点③:文本层当尺子纠 OCR/VLM 错字并回写 kb_raw_data(原文干净地基)。
    # 必须在实体抽取/打齐前做;失败不拖垮 graph 主流程。
    try:
        纠 = await 纠错回写(db, int(doc.id), int(doc.owner_id))
        if 纠.get("回写数") or 纠.get("纠正数"):
            result_patch = {
                "node03_纠正数": 纠.get("纠正数"),
                "node03_回写数": 纠.get("回写数"),
                "node03_留言数": 纠.get("留言数"),
            }
        else:
            result_patch = {"node03_status": 纠.get("status")}
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %d 节点③三路纠错失败(不影响graph): %s", int(doc.id), exc)
        result_patch = {"node03_error": str(exc)[:120]}

    # 节点⑦:抽取+当场定类+同文档归并(替换原 process_document_entities_from_fusions)
    result = await 串联(db, int(doc.id), int(doc.owner_id))
    result.update(result_patch)
    await db.refresh(doc)
    doc.graph_status = "degraded" if result.get("status") == "degraded" else "done"
    return {"status": doc.graph_status, **result}
