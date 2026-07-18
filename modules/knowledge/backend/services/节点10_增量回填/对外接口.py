# -*- coding: utf-8 -*-
"""节点⑩ 唯一对外接口（deferred）。

函数：回填(db, 新document_id, owner_id) -> dict
当前仅骨架，返回 {"status":"deferred"}。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def 回填(
    db: AsyncSession,
    新document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """新文档牵连旧文档信息回填。等⑦⑧⑨就绪后激活。"""
    _ = db
    return {
        "status": "deferred",
        "document_id": int(新document_id),
        "owner_id": int(owner_id),
        "reason": "等节点⑦⑧验证干净且⑨设计落地后再激活",
    }
