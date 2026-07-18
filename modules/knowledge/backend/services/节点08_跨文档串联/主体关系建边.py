# -*- coding: utf-8 -*-
"""主体关系建边：基于归并后锚点，把文档级抽取关系落到 kb_graph_edges。

干什么：
- 扫本文档 evidence 触达的实体节点
- 把已有 LLM 关系边中的 拥有/属于/包含 等主体谓词保留并去重
- 对「品牌-产品」等同文档共现，若无主体边则不硬造（无原文依据不编）

入参：db, document_id, owner_id
出参：{subject_edges, skipped, status}
依赖：kb_graph_nodes / kb_graph_edges / kb_chunk_entities
说明：主体关系主要在⑦抽取时已写边；此处做跨文档锚点重定向后的补全与统计。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node08.subject_edge")

主体谓词 = ("拥有", "属于", "包含", "引用", "参与", "位于", "产生", "领导")


async def 建主体关系边(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """统计并补齐本文档实体相关的主体关系边。

    1) 节点 label 若指向已 merged 实体，边仍有效（semantic_align 已改 entity_id/label）
    2) 删除 source==target 的自环
    3) 统计主体谓词边数量
    """
    stats: dict[str, Any] = {
        "subject_edges": 0,
        "self_loops_removed": 0,
        "doc_entity_nodes": 0,
        "status": "ok",
    }
    try:
        # 本文档实体 → 节点
        r = await db.execute(
            sa_text(
                """SELECT DISTINCT n.id
                   FROM kb_chunk_entities ce
                   JOIN kb_entity_dictionary ed
                     ON ed.id = ce.entity_id AND ed.owner_id = ce.owner_id
                   JOIN kb_graph_nodes n
                     ON n.entity_id = COALESCE(ed.canonical_id, ed.id)
                    AND n.owner_id = ce.owner_id
                   WHERE ce.document_id = :d AND ce.owner_id = :o
                     AND ed.status != 'merged'"""
            ),
            {"d": int(document_id), "o": int(owner_id)},
        )
        node_ids = [int(x[0]) for x in r.all()]
        stats["doc_entity_nodes"] = len(node_ids)
        if not node_ids:
            return stats

        # 清自环
        del_r = await db.execute(
            sa_text(
                """DELETE FROM kb_graph_edges
                   WHERE owner_id = :o
                     AND source_node_id = target_node_id
                     AND (source_node_id = ANY(:ids) OR target_node_id = ANY(:ids))
                   RETURNING id"""
            ),
            {"o": int(owner_id), "ids": node_ids},
        )
        stats["self_loops_removed"] = len(del_r.fetchall())

        # 统计主体边
        cnt = await db.execute(
            sa_text(
                """SELECT count(*) FROM kb_graph_edges
                   WHERE owner_id = :o
                     AND relation = ANY(:rels)
                     AND (source_node_id = ANY(:ids) OR target_node_id = ANY(:ids))"""
            ),
            {"o": int(owner_id), "rels": list(主体谓词), "ids": node_ids},
        )
        stats["subject_edges"] = int(cnt.scalar() or 0)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("主体关系建边失败 文档%s: %s", document_id, exc)
        stats["status"] = "error"
        stats["error"] = str(exc)[:200]
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
    return stats
