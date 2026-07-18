# -*- coding: utf-8 -*-
"""关联文档发现（骨架 deferred）。

设计：新文档入库后，按主体实体/文档关系找出相关旧文档。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def 发现关联文档(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    _ = (db, document_id, owner_id)
    return {"status": "deferred", "module": "关联文档发现"}
