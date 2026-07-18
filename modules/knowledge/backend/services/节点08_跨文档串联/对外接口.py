# -*- coding: utf-8 -*-
"""节点⑧ 唯一对外接口。

函数：跨文档串联(db, document_id, owner_id) -> dict
流程：跨文档实体归并 → 主体关系建边 → 相似边门禁
relations 阶段只调本接口。
"""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .主体关系建边 import 建主体关系边
from .相似边门禁 import 相似边门禁
from .跨文档实体归并 import 跨文档归并

logger = logging.getLogger("v2.knowledge.node08")


async def 跨文档串联(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """跨文档纠偏串联。失败不拖垮：单步记错继续。"""
    t0 = perf_counter()
    统计: dict[str, Any] = {
        "document_id": int(document_id),
        "owner_id": int(owner_id),
        "status": "ok",
    }

    try:
        并 = await 跨文档归并(db, int(document_id), int(owner_id))
        统计["merge"] = {
            "checked": 并.get("checked"),
            "merged": 并.get("merged"),
            "exact_name_merged": 并.get("exact_name_merged"),
            "details": (并.get("details") or [])[:15],
            "status": 并.get("status"),
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("节点⑧归并失败: %s", exc)
        统计["merge"] = {"status": "error", "error": str(exc)[:120]}

    try:
        边 = await 建主体关系边(db, int(document_id), int(owner_id))
        统计["subject_edges"] = 边
    except Exception as exc:  # noqa: BLE001
        logger.warning("节点⑧主体边失败: %s", exc)
        统计["subject_edges"] = {"status": "error", "error": str(exc)[:120]}

    try:
        门 = await 相似边门禁(db, int(document_id), int(owner_id))
        统计["similarity_gate"] = 门
        # 扁平字段便于验收
        gr = (门 or {}).get("graph_related") or {}
        统计["related_before"] = gr.get("before")
        统计["related_after"] = gr.get("after")
        统计["related_pruned"] = int(gr.get("pruned_low_weight") or 0) + int(
            gr.get("pruned_noise") or 0
        )
        fr = (门 or {}).get("file_relations") or {}
        统计["relations_created"] = fr.get("kept_file_relations") or fr.get(
            "relations_created_raw"
        ) or 0
    except Exception as exc:  # noqa: BLE001
        logger.warning("节点⑧门禁失败: %s", exc)
        统计["similarity_gate"] = {"status": "error", "error": str(exc)[:120]}
        统计["relations_created"] = 0

    统计["timing"] = {"stage_wall_ms": round((perf_counter() - t0) * 1000)}
    logger.info(
        "节点⑧ 文档%s: merged=%s related %s→%s file_rel=%s",
        document_id,
        (统计.get("merge") or {}).get("merged"),
        统计.get("related_before"),
        统计.get("related_after"),
        统计.get("relations_created"),
    )
    return 统计


async def compute_cross_document_chain(
    db: AsyncSession, document_id: int, owner_id: int, **_: object
) -> dict:
    return await 跨文档串联(db, document_id, owner_id)
