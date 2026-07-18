# -*- coding: utf-8 -*-
"""冲突消解（骨架 deferred）。

设计：跨文档信息冲突（A 说 5 品牌 B 说 6 品牌）消解。
激活前置：主体聚合可用 + 证据链完整。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def 消解冲突(
    db: AsyncSession,
    entity_id: int,
    owner_id: int,
) -> dict[str, Any]:
    _ = (db, entity_id, owner_id)
    return {"status": "deferred", "module": "冲突消解"}
