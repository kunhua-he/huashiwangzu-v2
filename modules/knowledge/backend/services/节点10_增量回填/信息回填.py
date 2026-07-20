# -*- coding: utf-8 -*-
"""信息回填：把新文档增量合并进主体视图（不改 fused_text/raw）。"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbEntitySubjectView
from ..节点09_二次融合 import 二次融合
from .防循环幂等 import 是否允许回填, 计算claim_hash, 记录回填

logger = logging.getLogger("v2.knowledge.node10.回填信息")

_SQL_DOC_ATTRS = """
SELECT page, attributes_json, id AS page_fusion_id
FROM kb_page_fusions
WHERE document_id = :d AND owner_id = :o
  AND attributes_json IS NOT NULL
ORDER BY page
LIMIT 500
"""


def _as_dict(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


async def 回填信息(
    db: AsyncSession,
    新document_id: int,
    旧document_id: int,
    owner_id: int,
    entity_id: int,
    *,
    提交: bool = True,
    depth: int = 1,
    max_depth: int = 1,
    seen: set[tuple[int, int, str]] | None = None,
) -> dict[str, Any]:
    """对共享实体：允许的 claims 合并后只触发一次 二次融合。"""
    src = int(新document_id)
    tgt = int(旧document_id)
    oid = int(owner_id)
    eid = int(entity_id)

    rows = (await db.execute(text(_SQL_DOC_ATTRS), {"d": src, "o": oid})).mappings().all()
    claims: list[dict[str, Any]] = []
    for row in rows:
        attrs = _as_dict(row["attributes_json"])
        for key, value in attrs.items():
            if str(key).startswith("_"):
                continue
            claims.append(
                {
                    "field": str(key),
                    "value": value,
                    "document_id": src,
                    "page": int(row["page"]) if row["page"] is not None else None,
                    "page_fusion_id": int(row["page_fusion_id"]) if row["page_fusion_id"] else None,
                    "entity_id": eid,
                    "related_document_id": tgt,
                }
            )

    if not claims:
        claims = [
            {
                "field": "__shared_entity__",
                "value": eid,
                "document_id": src,
                "related_document_id": tgt,
                "entity_id": eid,
            }
        ]

    allowed_claims: list[tuple[str, dict[str, Any]]] = []
    skipped = 0
    details: list[dict[str, Any]] = []
    for claim in claims:
        ch = 计算claim_hash(claim)
        gate = await 是否允许回填(
            db,
            oid,
            src,
            tgt,
            ch,
            depth=depth,
            max_depth=max_depth,
            seen=seen,
        )
        if not gate.get("allowed"):
            skipped += 1
            reason = str(gate.get("reason") or "blocked")
            details.append({"claim_hash": ch, "status": "skipped", "reason": reason})
            # 已在 ledger / reverse / seen 的不再重复写，避免唯一键冲突
            if 提交 and reason not in {
                "ledger_forward_exists",
                "ledger_reverse_exists",
                "seen_in_memory",
            }:
                await 记录回填(
                    db,
                    oid,
                    src,
                    tgt,
                    ch,
                    entity_id=eid,
                    depth=depth,
                    status="skipped",
                    diagnostics={"reason": reason, "claim": claim},
                    提交=True,
                )
            if seen is not None:
                seen.add((src, tgt, ch))
            continue
        allowed_claims.append((ch, claim))

    applied = 0
    fuse_result: dict[str, Any] | None = None
    if allowed_claims:
        fuse_result = await 二次融合(db, eid, oid, 提交=提交)
        for ch, claim in allowed_claims:
            applied += 1
            details.append(
                {
                    "claim_hash": ch,
                    "status": "applied",
                    "entity_id": eid,
                    "view_status": fuse_result.get("status"),
                    "view_id": fuse_result.get("view_id"),
                }
            )
            if 提交:
                await 记录回填(
                    db,
                    oid,
                    src,
                    tgt,
                    ch,
                    entity_id=eid,
                    depth=depth,
                    status="applied",
                    diagnostics={"claim": claim, "view_id": fuse_result.get("view_id")},
                    提交=True,
                )
            if seen is not None:
                seen.add((src, tgt, ch))

    view_row = (
        await db.execute(
            select(KbEntitySubjectView.id).where(
                KbEntitySubjectView.owner_id == oid,
                KbEntitySubjectView.entity_id == eid,
            )
        )
    ).scalar_one_or_none()

    return {
        "status": "ok" if applied else ("empty" if not claims else "skipped"),
        "src_document_id": src,
        "tgt_document_id": tgt,
        "entity_id": eid,
        "applied": applied,
        "skipped": skipped,
        "view_id": int(view_row) if view_row is not None else (
            int(fuse_result["view_id"]) if fuse_result and fuse_result.get("view_id") else None
        ),
        "details": details,
    }
