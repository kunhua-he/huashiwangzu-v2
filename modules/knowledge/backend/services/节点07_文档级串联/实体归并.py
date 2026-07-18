# -*- coding: utf-8 -*-
"""实体归并：同文档内变体归并到锚点。

干什么：
1. 同名/字级权威变体 → canonical_id + aliases + merge_log
2. 复用 semantic_align_service.canonicalize_name + _merge_variant_into

入参：db, document_id, owner_id
出参：{checked, merged, details}
依赖：semantic_align_service（字级权威）
说明：跨文档归并在节点⑧，本文件只做文档内。
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("v2.knowledge.node07.merge")


async def 同文档归并(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
) -> dict[str, Any]:
    """文档内实体变体归并。幂等：已 merged 跳过。"""
    # 延迟 import：外部禁止直接 import 本文件子符号；此处允许内部复用老服务
    from ..semantic_align_service import (
        _merge_variant_into,
        _resolve_canonical_entity,
        canonicalize_name,
    )

    stats: dict[str, Any] = {
        "checked": 0,
        "merged": 0,
        "details": [],
        "status": "ok",
    }
    try:
        r = await db.execute(
            sa_text(
                """SELECT DISTINCT ed.id, ed.name, ed.category, ed.type_id
                   FROM kb_chunk_entities ce
                   JOIN kb_entity_dictionary ed
                     ON ed.id = ce.entity_id AND ed.owner_id = ce.owner_id
                   WHERE ce.document_id = :d AND ce.owner_id = :o
                     AND ed.status != 'merged'
                   ORDER BY ed.id"""
            ),
            {"d": int(document_id), "o": int(owner_id)},
        )
        entities = [
            (int(eid), str(name or ""), str(cat or "通用"), type_id)
            for eid, name, cat, type_id in r.all()
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("文档 %s 拉实体失败: %s", document_id, exc)
        stats["status"] = "error"
        stats["error"] = str(exc)[:200]
        return stats

    # 1) 同文档完全同名多 id（极少见）→ 并到最小 id
    by_name: dict[str, list[tuple[int, str, Any]]] = {}
    for eid, name, cat, type_id in entities:
        by_name.setdefault(name, []).append((eid, cat, type_id))
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda x: x[0])
        anchor_id, anchor_cat, _ = group_sorted[0]
        for vid, _cat, _tid in group_sorted[1:]:
            try:
                await _merge_variant_into(
                    db, owner_id, vid, name, anchor_id, name,
                    [{"pos": -1, "from": name, "to": name, "reason": "同文档同名"}],
                )
                stats["merged"] += 1
                stats["details"].append({"from": name, "to": name, "variant_id": vid, "canonical_id": anchor_id, "kind": "同名"})
            except Exception as exc:  # noqa: BLE001
                logger.warning("同名归并失败 %s(%s→%s): %s", name, vid, anchor_id, exc)

    # 2) 字级权威：OCR 变体 → 规范名
    # 重新拉未 merged
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
            canonical_name, fixes = await canonicalize_name(db, owner_id, str(name or ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning("canonicalize 失败 %s: %s", name, exc)
            continue
        if not fixes or canonical_name == name:
            continue
        try:
            canonical_id = await _resolve_canonical_entity(
                db, owner_id, canonical_name, category or "通用"
            )
            await _merge_variant_into(
                db, owner_id, int(eid), str(name),
                int(canonical_id), str(canonical_name), fixes,
            )
            stats["merged"] += 1
            stats["details"].append({
                "from": name,
                "to": canonical_name,
                "variant_id": int(eid),
                "canonical_id": int(canonical_id),
                "kind": "字级权威",
                "fixes": fixes[:5],
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("变体归并失败 %s→%s: %s", name, canonical_name, exc)

    if stats["merged"]:
        try:
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("归并 commit 失败: %s", exc)
            stats["status"] = "commit_error"
            stats["error"] = str(exc)[:200]
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass

    logger.info(
        "节点⑦归并 文档%s: checked=%s merged=%s",
        document_id, stats["checked"], stats["merged"],
    )
    return stats
