# -*- coding: utf-8 -*-
"""节点⑩ 唯一对外接口。

函数：回填(db, 新document_id, owner_id, *, 提交=True, max_depth=1) -> dict
不挂 DAG；不改 pipeline_service。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .信息回填 import 回填信息
from .关联文档发现 import 发现关联文档

logger = logging.getLogger("v2.knowledge.node10")


async def 回填(
    db: AsyncSession,
    新document_id: int,
    owner_id: int,
    *,
    提交: bool = True,
    max_depth: int = 1,
) -> dict[str, Any]:
    """新文档牵连旧文档：刷新共享主体视图 + ledger 防循环。"""
    src = int(新document_id)
    oid = int(owner_id)
    found = await 发现关联文档(db, src, oid)
    related = found.get("related_documents") or []
    if not related:
        return {
            "status": "empty",
            "document_id": src,
            "owner_id": oid,
            "related_documents": [],
            "updated": 0,
            "skipped_cycles": 0,
            "details": [],
            "reason": "no_related_documents",
        }

    seen: set[tuple[int, int, str]] = set()
    details: list[dict[str, Any]] = []
    updated = 0
    skipped = 0
    # 每个关联文档 × 其共享实体
    for item in related:
        tgt = int(item["document_id"])
        entities = item.get("shared_entities") or []
        if not entities:
            continue
        for ent in entities:
            eid = int(ent["entity_id"])
            one = await 回填信息(
                db,
                src,
                tgt,
                oid,
                eid,
                提交=提交,
                depth=1,
                max_depth=max_depth,
                seen=seen,
            )
            details.append(one)
            updated += int(one.get("applied") or 0)
            skipped += int(one.get("skipped") or 0)

    status = "ok" if updated else ("empty" if not details else "skipped")
    logger.info(
        "回填 new_doc=%s related=%s updated=%s skipped=%s",
        src,
        len(related),
        updated,
        skipped,
    )
    return {
        "status": status,
        "document_id": src,
        "owner_id": oid,
        "related_documents": related,
        "updated": updated,
        "skipped_cycles": skipped,
        "details": details,
    }
