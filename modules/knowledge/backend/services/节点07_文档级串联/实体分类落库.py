# -*- coding: utf-8 -*-
"""实体分类落库：type_name → type_id → 写 kb_entity_dictionary，并建图/证据。

干什么：
- 查 kb_semantic_types 把 type_name 映到 type_id
- confidence < 0.6 → status=pending_review，不直接 confirmed
- 写实体词典 / 图谱节点 / chunk_entity / evidence / 关系边
- 幂等：重跑前清本文档 evidence/chunk_entity/governance 及独占节点边

入参：db, document_id, owner_id, entities, relationships
出参：{entities_found, relationships_found, typed, pending_review, skipped_low_conf, ...}
依赖：models / analysis_artifact_service
复用：entity_service 写图逻辑骨架，增加 type_id 与置信度门。
"""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..analysis_artifact_service import resolve_stage_prompt_hash, stable_hash
from ..model_routing import resolve_knowledge_concurrency

logger = logging.getLogger("v2.knowledge.node07.classify")

置信度门槛 = 0.6
写图批大小默认 = 50


def _fusion_source_hash(fusion, raw_rows: list) -> str:
    return stable_hash({
        "page_fusion_id": getattr(fusion, "id", None),
        "page": getattr(fusion, "page", None),
        "fused_text": getattr(fusion, "fused_text", ""),
        "raw_hashes": [getattr(row, "content_hash", None) for row in raw_rows],
    })


async def _加载类型映射(db: AsyncSession, owner_id: int) -> dict[str, int]:
    """type_name → type_id。优先本 owner，再全局(owner 不限)。"""
    from ...models import KbSemanticType

    r = await db.execute(
        select(KbSemanticType.id, KbSemanticType.type_name, KbSemanticType.owner_id)
        .where(KbSemanticType.status == "active")
        .order_by(KbSemanticType.owner_id.desc(), KbSemanticType.id)
    )
    映射: dict[str, int] = {}
    for tid, tname, oid in r.all():
        name = str(tname or "").strip()
        if not name:
            continue
        # 本 owner 覆盖全局
        if name not in 映射 or int(oid) == int(owner_id):
            映射[name] = int(tid)
    return 映射


async def _清文档旧图(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> int:
    """清本文档证据/chunk关联/治理候选及仅由这些实体撑起的节点边。"""
    from ...models import (
        KbChunkEntity,
        KbEvidence,
        KbGovernanceCandidate,
        KbGraphEdge,
        KbGraphNode,
    )

    t0 = perf_counter()
    old_evidence_entity_r = await db.execute(
        select(KbEvidence.entity_id).where(KbEvidence.document_id == document_id)
    )
    old_entity_ids = {row[0] for row in old_evidence_entity_r.all()}
    await db.execute(sa_delete(KbEvidence).where(KbEvidence.document_id == document_id))
    await db.execute(sa_delete(KbChunkEntity).where(KbChunkEntity.document_id == document_id))
    await db.execute(
        sa_delete(KbGovernanceCandidate).where(KbGovernanceCandidate.document_id == document_id)
    )
    if old_entity_ids:
        node_ids_r = await db.execute(
            select(KbGraphNode.id).where(
                KbGraphNode.entity_id.in_(old_entity_ids),
                KbGraphNode.owner_id == owner_id,
            )
        )
        node_ids = [row[0] for row in node_ids_r.all()]
        if node_ids:
            await db.execute(
                sa_delete(KbGraphEdge).where(
                    (KbGraphEdge.source_node_id.in_(node_ids))
                    | (KbGraphEdge.target_node_id.in_(node_ids))
                )
            )
            await db.execute(
                sa_delete(KbGraphNode).where(
                    KbGraphNode.entity_id.in_(old_entity_ids),
                    KbGraphNode.owner_id == owner_id,
                )
            )
    await db.commit()
    return round((perf_counter() - t0) * 1000)


async def 分类落库(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    entities: list[dict],
    relationships: list[dict],
    *,
    page_model_used: dict | None = None,
    page_model_diagnostics: dict | None = None,
) -> dict[str, Any]:
    """把抽取结果落 type_id + 图谱。低置信进 pending_review。"""
    from ...models import (
        KbChunk,
        KbChunkEntity,
        KbEntityDictionary,
        KbEvidence,
        KbGovernanceCandidate,
        KbGraphEdge,
        KbGraphNode,
        KbPageFusion,
        KbRawData,
    )

    page_model_used = page_model_used or {}
    page_model_diagnostics = page_model_diagnostics or {}
    stats: dict[str, Any] = {
        "entities_found": 0,
        "relationships_found": 0,
        "typed": 0,
        "pending_review": 0,
        "skipped_empty": 0,
        "errors": [],
        "entity_name_to_id": {},
        "样例": [],
    }

    类型映射 = await _加载类型映射(db, owner_id)
    if not 类型映射:
        stats["errors"].append("kb_semantic_types 为空，无法定类")

    fusion_r = await db.execute(
        select(KbPageFusion)
        .where(
            KbPageFusion.document_id == document_id,
            KbPageFusion.owner_id == owner_id,
        )
        .order_by(KbPageFusion.page)
    )
    fusion_by_page = {int(pf.page): pf for pf in fusion_r.scalars().all()}
    raw_rows_r = await db.execute(
        select(KbRawData)
        .where(KbRawData.document_id == document_id, KbRawData.owner_id == owner_id)
        .order_by(KbRawData.page, KbRawData.round, KbRawData.id)
    )
    page_to_raw: dict[int, list] = {}
    for raw in raw_rows_r.scalars().all():
        page_to_raw.setdefault(int(raw.page), []).append(raw)

    graph_prompt_hash = await resolve_stage_prompt_hash(db, "graph")
    cleanup_ms = await _清文档旧图(db, document_id, owner_id)
    stats["cleanup_ms"] = cleanup_ms

    # 去重：同 name 保留置信度更高、描述更长者
    seen: dict[str, dict] = {}
    for ent in entities:
        name = (ent.get("name") or "").strip()
        if not name:
            stats["skipped_empty"] += 1
            continue
        prev = seen.get(name)
        if prev is None or float(ent.get("confidence") or 0) > float(prev.get("confidence") or 0):
            seen[name] = ent
        elif prev is not None and len(str(ent.get("description") or "")) > len(
            str(prev.get("description") or "")
        ):
            # 置信度持平则拼描述
            if float(ent.get("confidence") or 0) == float(prev.get("confidence") or 0):
                prev["description"] = (prev.get("description") or "") or ent.get("description")

    entity_names = sorted(seen.keys())
    existing_by_name: dict[str, KbEntityDictionary] = {}
    if entity_names:
        er = await db.execute(
            select(KbEntityDictionary)
            .where(
                KbEntityDictionary.owner_id == owner_id,
                KbEntityDictionary.name.in_(entity_names),
            )
            .order_by(KbEntityDictionary.id)
        )
        for e in er.scalars().all():
            existing_by_name.setdefault(str(e.name), e)

    existing_node_entity_ids: set[int] = set()
    if existing_by_name:
        ids = [int(e.id) for e in existing_by_name.values()]
        nr = await db.execute(
            select(KbGraphNode.entity_id).where(
                KbGraphNode.owner_id == owner_id,
                KbGraphNode.entity_id.in_(ids),
            )
        )
        existing_node_entity_ids = {int(x[0]) for x in nr.all()}
    await db.commit()

    write_every = resolve_knowledge_concurrency(
        "graph_write_batch", 写图批大小默认, minimum=1, maximum=200
    )
    pending = 0
    entity_name_to_id: dict[str, int] = {}
    seen_candidates: set[str] = set()

    for name, ent in seen.items():
        type_name = (ent.get("type_name") or ent.get("category") or "噪音").strip()
        type_id = 类型映射.get(type_name)
        conf = float(ent.get("confidence") or 0.0)
        description = str(ent.get("description") or "")[:2000]
        category = type_name  # category 同步 type_name，便于旧 UI

        if conf < 置信度门槛:
            status = "pending_review"
            stats["pending_review"] += 1
        else:
            status = "candidate"

        existing = existing_by_name.get(name)
        if existing:
            entity_id = int(existing.id)
            entity_name_to_id[name] = entity_id
            # 补 type_id / 描述 / 状态（不覆盖 merged）
            if existing.status != "merged":
                if type_id and not existing.type_id:
                    existing.type_id = type_id
                    stats["typed"] += 1
                elif type_id and existing.type_id != type_id:
                    existing.type_id = type_id
                    stats["typed"] += 1
                elif type_id:
                    stats["typed"] += 1
                existing_desc = existing.description or ""
                if len(description) > len(existing_desc):
                    existing.description = description
                if existing.category in ("", "通用", None) or existing.category != category:
                    existing.category = category
                # 低置信只在原 status 非 confirmed/merged 时降为 pending_review
                if status == "pending_review" and existing.status in (
                    "candidate",
                    "pending",
                    "pending_review",
                    "",
                ):
                    existing.status = "pending_review"
                meta = dict(existing.semantic_meta or {}) if isinstance(existing.semantic_meta, dict) else {}
                meta.update({
                    "type_name": type_name,
                    "confidence": conf,
                    "source": "node07_extraction",
                })
                existing.semantic_meta = meta
            if entity_id not in existing_node_entity_ids and status != "pending_review":
                db.add(KbGraphNode(
                    owner_id=owner_id,
                    entity_id=entity_id,
                    label=name,
                    category=category,
                    description=description,
                ))
                existing_node_entity_ids.add(entity_id)
        else:
            # 低置信：仍落词典(便于人工审)，但不建图节点
            rec = KbEntityDictionary(
                owner_id=owner_id,
                name=name,
                category=category,
                description=description,
                status=status,
                source="node07_extraction",
                type_id=type_id,
                semantic_meta={
                    "type_name": type_name,
                    "confidence": conf,
                    "source": "node07_extraction",
                },
            )
            db.add(rec)
            await db.flush()
            entity_id = int(rec.id)
            entity_name_to_id[name] = entity_id
            existing_by_name[name] = rec
            if type_id:
                stats["typed"] += 1
            if status != "pending_review":
                db.add(KbGraphNode(
                    owner_id=owner_id,
                    entity_id=entity_id,
                    label=name,
                    category=category,
                    description=description,
                ))
                existing_node_entity_ids.add(entity_id)

        if name not in seen_candidates:
            seen_candidates.add(name)
            db.add(KbGovernanceCandidate(
                owner_id=owner_id,
                document_id=document_id,
                entity_name=name,
                category=category,
                excerpt=description[:500],
                confidence=conf,
                audit_status="pending",
            ))

        if len(stats["样例"]) < 12:
            stats["样例"].append({
                "name": name,
                "type_name": type_name,
                "type_id": type_id,
                "confidence": conf,
                "status": status,
                "entity_id": entity_name_to_id.get(name),
            })

        pending += 1
        if pending >= write_every:
            await db.commit()
            pending = 0

    await db.commit()
    stats["entities_found"] = len(entity_name_to_id)
    stats["entity_name_to_id"] = entity_name_to_id

    # chunk / evidence
    chunks_r = await db.execute(
        select(KbChunk)
        .where(KbChunk.document_id == document_id, KbChunk.owner_id == owner_id)
        .order_by(KbChunk.page, KbChunk.chunk_index)
    )
    page_to_chunks: dict[int, list[int]] = {}
    for ch in chunks_r.scalars().all():
        page_to_chunks.setdefault(ch.page or 0, []).append(int(ch.id))

    seen_ev: set[tuple[int, int]] = set()
    seen_ce: set[tuple[int, int]] = set()
    pending = 0
    for ent in entities:
        name = (ent.get("name") or "").strip()
        entity_id = entity_name_to_id.get(name)
        if not entity_id:
            continue
        # 低置信不写证据/chunk 关联，避免污染检索
        if float(ent.get("confidence") or 0) < 置信度门槛:
            continue
        page = int(ent.get("page") or 0)
        chunk_ids = page_to_chunks.get(page, [])
        ev_key = (entity_id, page)
        if ev_key not in seen_ev:
            seen_ev.add(ev_key)
            fusion = fusion_by_page.get(page)
            raw_rows = page_to_raw.get(page, [])
            db.add(KbEvidence(
                owner_id=owner_id,
                entity_id=entity_id,
                document_id=document_id,
                chunk_id=chunk_ids[0] if chunk_ids else 0,
                page=page,
                excerpt=str(ent.get("description") or "")[:500],
                confidence=float(ent.get("confidence") or 0.7),
                status="pending",
                raw_data_id=int(raw_rows[0].id) if raw_rows else None,
                page_fusion_id=int(fusion.id) if fusion is not None else None,
                source_round="fusion",
                claim_type="entity",
                source_hash=_fusion_source_hash(fusion, raw_rows) if fusion is not None else None,
                prompt_hash=graph_prompt_hash,
                model_used=page_model_used.get(page),
                diagnostics_json={
                    "model_diagnostics": page_model_diagnostics.get(page),
                    "type_name": ent.get("type_name"),
                    "source": "node07",
                },
            ))
            pending += 1
        for cid in chunk_ids:
            ce_key = (entity_id, cid)
            if ce_key in seen_ce:
                continue
            seen_ce.add(ce_key)
            db.add(KbChunkEntity(
                owner_id=owner_id,
                chunk_id=cid,
                entity_id=entity_id,
                document_id=document_id,
                confidence=float(ent.get("confidence") or 0.7),
            ))
            pending += 1
        if pending >= write_every:
            await db.commit()
            pending = 0
    await db.commit()

    # 关系边
    rel_names = set()
    for rel in relationships:
        s = (rel.get("source") or "").strip()
        t = (rel.get("target") or "").strip()
        if s and t:
            rel_names.add(s)
            rel_names.add(t)
    nodes_by_label: dict[str, KbGraphNode] = {}
    existing_edge_keys: set[tuple[int, int, str]] = set()
    if rel_names:
        nr = await db.execute(
            select(KbGraphNode).where(
                KbGraphNode.owner_id == owner_id,
                KbGraphNode.label.in_(list(rel_names)),
            )
        )
        for node in nr.scalars().all():
            nodes_by_label.setdefault(str(node.label), node)
        nids = [int(n.id) for n in nodes_by_label.values()]
        if nids:
            er = await db.execute(
                select(
                    KbGraphEdge.source_node_id,
                    KbGraphEdge.target_node_id,
                    KbGraphEdge.relation,
                ).where(
                    KbGraphEdge.owner_id == owner_id,
                    KbGraphEdge.source_node_id.in_(nids),
                    KbGraphEdge.target_node_id.in_(nids),
                )
            )
            existing_edge_keys = {
                (int(a), int(b), str(c)) for a, b, c in er.all()
            }
    await db.commit()

    seen_rel: set[str] = set()
    pending = 0
    for rel in relationships:
        s = (rel.get("source") or "").strip()
        t = (rel.get("target") or "").strip()
        predicate = (rel.get("predicate") or rel.get("relation") or "相关").strip()
        key = f"{s}|{t}|{predicate}"
        if key in seen_rel or not s or not t:
            continue
        seen_rel.add(key)
        src = nodes_by_label.get(s)
        tgt = nodes_by_label.get(t)
        if not src or not tgt:
            continue
        edge_key = (int(src.id), int(tgt.id), predicate)
        if edge_key in existing_edge_keys:
            continue
        db.add(KbGraphEdge(
            owner_id=owner_id,
            source_node_id=src.id,
            target_node_id=tgt.id,
            relation=predicate,
            weight=1.0,
            description=str(rel.get("evidence") or rel.get("description") or "")[:500],
        ))
        existing_edge_keys.add(edge_key)
        pending += 1
        if pending >= write_every:
            await db.commit()
            pending = 0
    stats["relationships_found"] = len(seen_rel)
    await db.commit()
    return stats
