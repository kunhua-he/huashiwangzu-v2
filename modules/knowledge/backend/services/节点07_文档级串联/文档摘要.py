# -*- coding: utf-8 -*-
"""文档摘要：复用 profile_service.generate_document_profile。

干什么：薄封装，失败不抛到主流程。
入参：db, document_id, owner_id
出参：profile 服务原 dict 或 {status:error}
依赖：profile_service
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node07.profile")


async def 生成摘要(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """复用文件画像服务。"""
    try:
        from ..profile_service import generate_document_profile

        return await generate_document_profile(db, int(document_id), int(owner_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %s 摘要失败: %s", document_id, exc)
        return {"status": "error", "error": str(exc)[:200], "document_id": int(document_id)}
