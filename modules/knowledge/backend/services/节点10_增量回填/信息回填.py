# -*- coding: utf-8 -*-
"""信息回填（骨架 deferred）。

设计：把新信息补进旧文档的聚合视图。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def 回填信息(
    db: AsyncSession,
    新document_id: int,
    旧document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    _ = (db, 新document_id, 旧document_id, owner_id)
    return {"status": "deferred", "module": "信息回填"}
