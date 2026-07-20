# -*- coding: utf-8 -*-
"""防循环幂等：ledger + 内存 seen，防 A↔B 死循环。"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbBackfillLedger

logger = logging.getLogger("v2.knowledge.node10.幂等")


def 计算claim_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


async def 是否允许回填(
    db: AsyncSession,
    owner_id: int,
    src_document_id: int,
    tgt_document_id: int,
    claim_hash: str,
    *,
    depth: int = 1,
    max_depth: int = 1,
    seen: set[tuple[int, int, str]] | None = None,
) -> dict[str, Any]:
    """检查是否允许 src→tgt 应用该 claim。"""
    src = int(src_document_id)
    tgt = int(tgt_document_id)
    oid = int(owner_id)
    ch = str(claim_hash)
    if src == tgt:
        return {"allowed": False, "reason": "same_document"}
    if depth > max_depth:
        return {"allowed": False, "reason": "depth_exceeded"}
    key = (src, tgt, ch)
    if seen is not None and key in seen:
        return {"allowed": False, "reason": "seen_in_memory"}

    exists = (
        await db.execute(
            select(KbBackfillLedger.id).where(
                KbBackfillLedger.owner_id == oid,
                KbBackfillLedger.src_document_id == src,
                KbBackfillLedger.tgt_document_id == tgt,
                KbBackfillLedger.claim_hash == ch,
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        return {"allowed": False, "reason": "ledger_forward_exists"}

    reverse = (
        await db.execute(
            select(KbBackfillLedger.id).where(
                KbBackfillLedger.owner_id == oid,
                KbBackfillLedger.src_document_id == tgt,
                KbBackfillLedger.tgt_document_id == src,
                KbBackfillLedger.claim_hash == ch,
            )
        )
    ).scalar_one_or_none()
    if reverse is not None:
        return {"allowed": False, "reason": "ledger_reverse_exists"}

    return {"allowed": True, "reason": "ok"}


async def 记录回填(
    db: AsyncSession,
    owner_id: int,
    src_document_id: int,
    tgt_document_id: int,
    claim_hash: str,
    *,
    entity_id: int | None = None,
    depth: int = 1,
    status: str = "applied",
    diagnostics: dict[str, Any] | None = None,
    提交: bool = True,
) -> bool:
    """写入 ledger；唯一键冲突视为已存在，返回 False。"""
    row = KbBackfillLedger(
        owner_id=int(owner_id),
        src_document_id=int(src_document_id),
        tgt_document_id=int(tgt_document_id),
        entity_id=int(entity_id) if entity_id is not None else None,
        claim_hash=str(claim_hash),
        direction="forward",
        depth=int(depth),
        status=status,
        diagnostics_json=diagnostics,
    )
    db.add(row)
    if not 提交:
        return True
    try:
        await db.commit()
        return True
    except IntegrityError:
        await db.rollback()
        logger.info(
            "ledger unique hit src=%s tgt=%s claim=%s",
            src_document_id,
            tgt_document_id,
            claim_hash,
        )
        return False
