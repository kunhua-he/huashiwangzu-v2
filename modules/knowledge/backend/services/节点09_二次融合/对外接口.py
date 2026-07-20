# -*- coding: utf-8 -*-
"""节点⑨ 唯一对外接口。

函数：二次融合(db, 主体entity_id, owner_id, *, 提交=True) -> dict
纯 DB 聚合 + 冲突标记；默认 UPSERT kb_entity_subject_views。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbEntitySubjectView
from .主体聚合 import 聚合主体
from .冲突消解 import 消解冲突

logger = logging.getLogger("v2.knowledge.node09")


async def 二次融合(
    db: AsyncSession,
    主体entity_id: int,
    owner_id: int,
    *,
    提交: bool = True,
) -> dict[str, Any]:
    """跨文档二次融合入口。不挂 DAG，可运维/脚本调用。"""
    eid = int(主体entity_id)
    oid = int(owner_id)
    agg = await 聚合主体(db, eid, oid)
    if agg.get("status") == "empty":
        return {
            "status": "empty",
            "entity_id": eid,
            "owner_id": oid,
            "reason": agg.get("reason") or "no_sources",
            "view": None,
            "written": False,
        }

    conflict = 消解冲突(agg)
    view = {
        "entity_id": agg["entity_id"],
        "entity_name": agg.get("entity_name"),
        "type_id": agg.get("type_id"),
        "category": agg.get("category"),
        "attributes": agg.get("attributes") or {},
        "conflicts": conflict.get("conflicts") or [],
        "evidence": agg.get("evidence") or [],
        "source_document_ids": agg.get("source_document_ids") or [],
        "page_count": agg.get("page_count") or 0,
        "document_count": agg.get("document_count") or 0,
        "content_hash": agg.get("content_hash"),
        "conflict_count": conflict.get("conflict_count") or 0,
    }

    written = False
    view_id = None
    if 提交:
        row = (
            await db.execute(
                select(KbEntitySubjectView).where(
                    KbEntitySubjectView.owner_id == oid,
                    KbEntitySubjectView.entity_id == int(agg["entity_id"]),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = KbEntitySubjectView(
                owner_id=oid,
                entity_id=int(agg["entity_id"]),
            )
            db.add(row)
        row.entity_name = agg.get("entity_name")
        row.type_id = agg.get("type_id")
        row.category = agg.get("category")
        row.attributes_json = agg.get("attributes") or {}
        row.conflicts_json = conflict.get("conflicts") or []
        row.evidence_json = (agg.get("evidence") or [])[:500]
        row.source_document_ids = agg.get("source_document_ids") or []
        row.page_count = int(agg.get("page_count") or 0)
        row.document_count = int(agg.get("document_count") or 0)
        row.content_hash = agg.get("content_hash")
        row.view_version = int(row.view_version or 0) + 1
        row.status = "active"
        row.diagnostics_json = {
            "requested_entity_id": eid,
            "conflict_count": conflict.get("conflict_count") or 0,
        }
        await db.commit()
        await db.refresh(row)
        written = True
        view_id = int(row.id)
        view["view_version"] = row.view_version
        view["id"] = view_id

    status = "degraded" if (conflict.get("conflict_count") or 0) > 0 else "ok"
    logger.info(
        "二次融合 entity=%s status=%s written=%s conflicts=%s",
        agg["entity_id"],
        status,
        written,
        conflict.get("conflict_count"),
    )
    return {
        "status": status,
        "entity_id": agg["entity_id"],
        "owner_id": oid,
        "requested_entity_id": eid,
        "view": view,
        "conflicts": conflict.get("conflicts") or [],
        "written": written,
        "view_id": view_id,
    }
