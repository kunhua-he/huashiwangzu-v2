# -*- coding: utf-8 -*-
"""相似边门禁：收紧 relation='相关' 与文档级弱相似边。

干什么：
1. 图谱边 kb_graph_edges.relation='相关'：
   - weight < 0.35 的直接删（垃圾相似）
   - 两端实体若都是噪音类型，删
2. 文档关系 kb_file_relations：
   - 阈值从 0.15 提到 0.35
   - 必须共享 ≥1 个非噪音主体实体才保留/新建
3. 仍调用原 compute_file_relations 做候选，但写边前过门禁

入参：db, document_id, owner_id
出参：{before_related, after_related, pruned_graph, file_relations, ...}
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node08.sim_gate")

相似阈值 = 0.35
最少共享主体 = 1


async def _非噪音实体集(db: AsyncSession, owner_id: int, entity_ids: set[int]) -> set[int]:
    if not entity_ids:
        return set()
    r = await db.execute(
        sa_text(
            """SELECT ed.id
               FROM kb_entity_dictionary ed
               LEFT JOIN kb_semantic_types st ON st.id = ed.type_id
               WHERE ed.owner_id = :o
                 AND ed.id = ANY(:ids)
                 AND ed.status != 'merged'
                 AND COALESCE(st.is_noise, false) = false
                 AND COALESCE(ed.category, '') NOT IN ('噪音', 'noise', '通用')
                 AND COALESCE(st.type_name, '') NOT IN ('噪音', '')"""
        ),
        {"o": int(owner_id), "ids": list(entity_ids)},
    )
    # 无 type 时：名称长度≥2 且不像纯数字，也算「可能主体」
    hit = {int(x[0]) for x in r.all()}
    if hit:
        return hit
    r2 = await db.execute(
        sa_text(
            """SELECT id FROM kb_entity_dictionary
               WHERE owner_id=:o AND id = ANY(:ids) AND status != 'merged'
                 AND length(name) >= 2
                 AND name !~ '^[0-9.#]+$'
                 AND category NOT IN ('噪音','noise')"""
        ),
        {"o": int(owner_id), "ids": list(entity_ids)},
    )
    return {int(x[0]) for x in r2.all()}


async def 收紧图谱相关边(
    db: AsyncSession,
    owner_id: int,
    document_id: int | None = None,
) -> dict[str, Any]:
    """砍低质量 relation='相关' 边。

    若给 document_id：只动本文档实体触达的节点边。
    否则全 owner（自测慎用）。
    """
    stats: dict[str, Any] = {
        "before": 0,
        "after": 0,
        "pruned_low_weight": 0,
        "pruned_noise": 0,
        "status": "ok",
    }
    try:
        if document_id is not None:
            scope_sql = """
                WITH doc_nodes AS (
                  SELECT DISTINCT n.id
                  FROM kb_chunk_entities ce
                  JOIN kb_graph_nodes n
                    ON n.entity_id = ce.entity_id AND n.owner_id = ce.owner_id
                  WHERE ce.document_id = :d AND ce.owner_id = :o
                )
            """
            before_q = scope_sql + """
                SELECT count(*) FROM kb_graph_edges e
                WHERE e.owner_id=:o AND e.relation='相关'
                  AND (e.source_node_id IN (SELECT id FROM doc_nodes)
                    OR e.target_node_id IN (SELECT id FROM doc_nodes))
            """
            params: dict[str, Any] = {"o": int(owner_id), "d": int(document_id)}
        else:
            before_q = """SELECT count(*) FROM kb_graph_edges
                         WHERE owner_id=:o AND relation='相关'"""
            params = {"o": int(owner_id)}

        stats["before"] = int((await db.execute(sa_text(before_q), params)).scalar() or 0)

        # 1) 低 weight
        if document_id is not None:
            del1 = await db.execute(
                sa_text(
                    """
                    WITH doc_nodes AS (
                      SELECT DISTINCT n.id
                      FROM kb_chunk_entities ce
                      JOIN kb_graph_nodes n
                        ON n.entity_id = ce.entity_id AND n.owner_id = ce.owner_id
                      WHERE ce.document_id = :d AND ce.owner_id = :o
                    )
                    DELETE FROM kb_graph_edges e
                    WHERE e.owner_id=:o AND e.relation='相关'
                      AND COALESCE(e.weight, 0) < :th
                      AND (e.source_node_id IN (SELECT id FROM doc_nodes)
                        OR e.target_node_id IN (SELECT id FROM doc_nodes))
                    RETURNING e.id
                    """
                ),
                {**params, "th": 相似阈值},
            )
        else:
            del1 = await db.execute(
                sa_text(
                    """DELETE FROM kb_graph_edges
                       WHERE owner_id=:o AND relation='相关'
                         AND COALESCE(weight,0) < :th
                       RETURNING id"""
                ),
                {**params, "th": 相似阈值},
            )
        stats["pruned_low_weight"] = len(del1.fetchall())

        # 2) 任一端是噪音，或两端都不是主体类型(品牌/产品/成分等) → 砍
        # 说明: LLM 写的相关边 weight 常=1.0, 单靠阈值砍不动 5 万垃圾边
        if document_id is not None:
            del2 = await db.execute(
                sa_text(
                    """
                    WITH doc_nodes AS (
                      SELECT DISTINCT n.id
                      FROM kb_chunk_entities ce
                      JOIN kb_graph_nodes n
                        ON n.entity_id = ce.entity_id AND n.owner_id = ce.owner_id
                      WHERE ce.document_id = :d AND ce.owner_id = :o
                    ),
                    node_flags AS (
                      SELECT n.id,
                        (COALESCE(st.is_noise,false)=true
                          OR ed.category IN ('噪音','noise')
                          OR st.type_name = '噪音'
                          OR ed.name ~ '^(主色|边缘密度|平均亮度|占比)'
                          OR length(ed.name) > 24) AS is_noise,
                        (COALESCE(st.type_name, ed.category) IN
                          ('品牌','产品','成分','原料','功效','品类','系列','组织','规格','人物')
                        ) AS is_subject
                      FROM kb_graph_nodes n
                      JOIN kb_entity_dictionary ed ON ed.id = n.entity_id
                      LEFT JOIN kb_semantic_types st ON st.id = ed.type_id
                      WHERE n.owner_id = :o
                    )
                    DELETE FROM kb_graph_edges e
                    WHERE e.owner_id=:o AND e.relation='相关'
                      AND (e.source_node_id IN (SELECT id FROM doc_nodes)
                        OR e.target_node_id IN (SELECT id FROM doc_nodes))
                      AND (
                        EXISTS (SELECT 1 FROM node_flags f WHERE f.id=e.source_node_id AND f.is_noise)
                        OR EXISTS (SELECT 1 FROM node_flags f WHERE f.id=e.target_node_id AND f.is_noise)
                        OR NOT (
                          EXISTS (SELECT 1 FROM node_flags f WHERE f.id=e.source_node_id AND f.is_subject)
                          AND EXISTS (SELECT 1 FROM node_flags f WHERE f.id=e.target_node_id AND f.is_subject)
                        )
                      )
                    RETURNING e.id
                    """
                ),
                params,
            )
        else:
            del2 = await db.execute(
                sa_text(
                    """
                    WITH node_flags AS (
                      SELECT n.id,
                        (COALESCE(st.is_noise,false)=true
                          OR ed.category IN ('噪音','noise')
                          OR st.type_name = '噪音'
                          OR ed.name ~ '^(主色|边缘密度|平均亮度|占比)'
                          OR length(ed.name) > 24) AS is_noise,
                        (COALESCE(st.type_name, ed.category) IN
                          ('品牌','产品','成分','原料','功效','品类','系列','组织','规格','人物')
                        ) AS is_subject
                      FROM kb_graph_nodes n
                      JOIN kb_entity_dictionary ed ON ed.id = n.entity_id
                      LEFT JOIN kb_semantic_types st ON st.id = ed.type_id
                      WHERE n.owner_id = :o
                    )
                    DELETE FROM kb_graph_edges e
                    WHERE e.owner_id=:o AND e.relation='相关'
                      AND (
                        EXISTS (SELECT 1 FROM node_flags f WHERE f.id=e.source_node_id AND f.is_noise)
                        OR EXISTS (SELECT 1 FROM node_flags f WHERE f.id=e.target_node_id AND f.is_noise)
                        OR NOT (
                          EXISTS (SELECT 1 FROM node_flags f WHERE f.id=e.source_node_id AND f.is_subject)
                          AND EXISTS (SELECT 1 FROM node_flags f WHERE f.id=e.target_node_id AND f.is_subject)
                        )
                      )
                    RETURNING e.id
                    """
                ),
                params,
            )
        stats["pruned_noise"] = len(del2.fetchall())

        stats["after"] = int((await db.execute(sa_text(before_q), params)).scalar() or 0)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("收紧相关边失败: %s", exc)
        stats["status"] = "error"
        stats["error"] = str(exc)[:200]
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
    return stats


async def 门禁文档关系(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """调用原 compute_file_relations 后，按 0.35 + 非噪音主体共现 清扫。"""
    stats: dict[str, Any] = {
        "relations_created_raw": 0,
        "pruned_file_relations": 0,
        "kept_file_relations": 0,
        "status": "ok",
    }
    try:
        from ..relation_service import compute_file_relations

        raw = await compute_file_relations(db, int(document_id), int(owner_id))
        stats["relations_created_raw"] = int(raw.get("relations_created") or 0)
        stats["raw_timing"] = raw.get("timing")
    except Exception as exc:  # noqa: BLE001
        logger.warning("compute_file_relations 失败: %s", exc)
        stats["status"] = "compute_error"
        stats["error"] = str(exc)[:200]
        return stats

    # 清扫：本文档相关边 score < 0.35 或 无非噪音共享实体
    try:
        # 先按阈值砍
        d1 = await db.execute(
            sa_text(
                """DELETE FROM kb_file_relations
                   WHERE owner_id=:o
                     AND (source_document_id=:d OR target_document_id=:d)
                     AND COALESCE(similarity_score, 0) < :th
                   RETURNING id"""
            ),
            {"o": int(owner_id), "d": int(document_id), "th": 相似阈值},
        )
        pruned = len(d1.fetchall())

        # 再查剩余边，检查共享实体是否含非噪音主体
        rows = await db.execute(
            sa_text(
                """SELECT id, source_document_id, target_document_id, shared_entities
                   FROM kb_file_relations
                   WHERE owner_id=:o
                     AND (source_document_id=:d OR target_document_id=:d)"""
            ),
            {"o": int(owner_id), "d": int(document_id)},
        )
        drop_ids: list[int] = []
        for rid, src, tgt, shared in rows.all():
            # shared_entities 是名字列表；解析为 entity id
            names = shared if isinstance(shared, list) else []
            if not names:
                drop_ids.append(int(rid))
                continue
            er = await db.execute(
                sa_text(
                    """SELECT id FROM kb_entity_dictionary
                       WHERE owner_id=:o AND name = ANY(:names) AND status != 'merged'"""
                ),
                {"o": int(owner_id), "names": [str(x) for x in names]},
            )
            eids = {int(x[0]) for x in er.all()}
            subject = await _非噪音实体集(db, owner_id, eids)
            if len(subject) < 最少共享主体:
                drop_ids.append(int(rid))

        if drop_ids:
            d2 = await db.execute(
                sa_text("DELETE FROM kb_file_relations WHERE id = ANY(:ids) RETURNING id"),
                {"ids": drop_ids},
            )
            pruned += len(d2.fetchall())

        kept = await db.execute(
            sa_text(
                """SELECT count(*) FROM kb_file_relations
                   WHERE owner_id=:o
                     AND (source_document_id=:d OR target_document_id=:d)"""
            ),
            {"o": int(owner_id), "d": int(document_id)},
        )
        stats["pruned_file_relations"] = pruned
        stats["kept_file_relations"] = int(kept.scalar() or 0)
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("门禁文档关系失败: %s", exc)
        stats["status"] = "gate_error"
        stats["error"] = str(exc)[:200]
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
    return stats


async def 相似边门禁(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """对外子步骤总入口。"""
    graph = await 收紧图谱相关边(db, owner_id, document_id=document_id)
    file_rel = await 门禁文档关系(db, document_id, owner_id)
    return {
        "graph_related": graph,
        "file_relations": file_rel,
        "threshold": 相似阈值,
        "status": "ok" if graph.get("status") == "ok" else graph.get("status"),
    }
