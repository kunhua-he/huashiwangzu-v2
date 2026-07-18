# -*- coding: utf-8 -*-
"""主体聚合（骨架 deferred）。

设计：同主体跨文档信息聚合成一个视图。
激活前置：⑦ type_id 可用、⑧ 碎节点归并验证通过。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def 聚合主体(
    db: AsyncSession,
    entity_id: int,
    owner_id: int,
) -> dict[str, Any]:
    _ = (db, entity_id, owner_id)
    return {"status": "deferred", "module": "主体聚合"}
