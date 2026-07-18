# -*- coding: utf-8 -*-
"""跨文档实体归并：同名/变体实体跨文档归一到锚点。

干什么：对本文档触达实体，在全 owner 范围内用字级权威 canonicalize，
把变体并入锚点（华世王镞 205 碎节点 → 1 锚点）。

入参：db, document_id, owner_id
出参：{checked, merged, details}
依赖：semantic_align_service
复用：canonicalize_name / _merge_variant_into / _resolve_canonical_entity
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node08.merge")


async def 跨文档归并(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """跨文档维度归并本文档相关实体。"""
    from ..semantic_align_service import (
        _merge_variant_into,
        _resolve_canonical_entity,
        canonicalize_name,
    )

    stats: dict[str, Any] = {
        "checked": 0,
        "merged": 0,
        "exact_name_merged": 0,
        "details": [],
        "status": "ok",
    }

    try:
        # 本文档触达的实体
        r = await db.execute(
            sa_text(
                """SELECT DISTINCT ed.id, ed.name, ed.category
                   FROM kb_chunk_entities ce
                   JOIN kb_entity_dictionary ed
                     ON ed.id = ce.entity_id AND ed.owner_id = ce.owner_id
                   WHERE ce.document_id = :d AND ce.owner_id = :o
                     AND ed.status != 'merged'
                   ORDER BY ed.id"""
            ),
            {"d": int(document_id), "o": int(owner_id)},
        )
        doc_entities = [(int(i), str(n or ""), str(c or "通用")) for i, n, c in r.all()]
    except Exception as exc:  # noqa: BLE001
        stats["status"] = "error"
        stats["error"] = str(exc)[:200]
        return stats

    # A) 精确同名：库中同 name 多条未 merged → 并到最小 id
    names = list({n for _, n, _ in doc_entities if n})
    for name in names:
        try:
            rr = await db.execute(
                sa_text(
                    """SELECT id, category FROM kb_entity_dictionary
                       WHERE owner_id=:o AND name=:n AND status != 'merged'
                       ORDER BY id"""
                ),
                {"o": int(owner_id), "n": name},
            )
            rows = [(int(i), str(c or "通用")) for i, c in rr.all()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("查同名失败 %s: %s", name, exc)
            continue
        if len(rows) < 2:
            continue
        anchor_id, anchor_cat = rows[0]
        for vid, _cat in rows[1:]:
            try:
                await _merge_variant_into(
                    db, owner_id, vid, name, anchor_id, name,
                    [{"pos": -1, "from": name, "to": name, "reason": "跨文档同名"}],
                )
                stats["merged"] += 1
                stats["exact_name_merged"] += 1
                if len(stats["details"]) < 30:
                    stats["details"].append({
                        "from": name, "to": name,
                        "variant_id": vid, "canonical_id": anchor_id,
                        "kind": "跨文档同名",
                    })
            except Exception as exc:  # noqa: BLE001
                logger.warning("跨文档同名归并失败 %s: %s", name, exc)

    # B) 字级权威变体
    r2 = await db.execute(
        sa_text(
            """SELECT DISTINCT ed.id, ed.name, ed.category
               FROM kb_chunk_entities ce
               JOIN kb_entity_dictionary ed
                 ON ed.id = ce.entity_id AND ed.owner_id = ce.owner_id
               WHERE ce.document_id = :d AND ce.owner_id = :o
                 AND ed.status != 'merged'"""
        ),
        {"d": int(document_id), "o": int(owner_id)},
    )
    for eid, name, category in r2.all():
        stats["checked"] += 1
        try:
            canonical_name, fixes = await canonicalize_name(
                db, int(owner_id), str(name or "")
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("canonicalize 失败 %s: %s", name, exc)
            continue
        if not fixes or canonical_name == name:
            continue
        try:
            canonical_id = await _resolve_canonical_entity(
                db, int(owner_id), str(canonical_name), category or "通用"
            )
            await _merge_variant_into(
                db, int(owner_id), int(eid), str(name),
                int(canonical_id), str(canonical_name), fixes,
            )
            stats["merged"] += 1
            if len(stats["details"]) < 30:
                stats["details"].append({
                    "from": name,
                    "to": canonical_name,
                    "variant_id": int(eid),
                    "canonical_id": int(canonical_id),
                    "kind": "字级权威",
                })
        except Exception as exc:  # noqa: BLE001
            logger.warning("跨文档变体归并失败 %s→%s: %s", name, canonical_name, exc)

    if stats["merged"]:
        try:
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            stats["status"] = "commit_error"
            stats["error"] = str(exc)[:200]
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass

    logger.info(
        "节点⑧归并 文档%s: checked=%s merged=%s exact=%s",
        document_id, stats["checked"], stats["merged"], stats["exact_name_merged"],
    )
    return stats
