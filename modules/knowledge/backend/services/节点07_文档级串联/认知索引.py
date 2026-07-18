# -*- coding: utf-8 -*-
"""认知索引：复用 cognitive_index_service.derive_document_cognitive_index。

干什么：薄封装，失败不抛到主流程。
入参：db, document_id, owner_id
出参：原 dict 或 {status:error}
依赖：cognitive_index_service
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node07.cognitive")


async def 建认知索引(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """复用认知索引派生。"""
    try:
        from ..cognitive_index_service import derive_document_cognitive_index

        return await derive_document_cognitive_index(
            db, owner_id=int(owner_id), document_id=int(document_id)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %s 认知索引失败: %s", document_id, exc)
        return {"status": "error", "error": str(exc)[:200], "document_id": int(document_id)}
