# -*- coding: utf-8 -*-
"""节点07A 唯一对外接口。

函数：
- 枚举文档(db, document_id, owner_id) -> dict
- 枚举(db, owner_id, document_ids=None, limit=None) -> dict  # 存量批跑

只做分词穷举落盘，不烧 LLM。
热路径：词库一次加载 + 内存累计 + 批量落库，禁止逐词 SELECT。
"""
from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument, KbPageFusion
from ._动态加载 import 取属性

# 中文模块名禁止静态 import
分句, 分词, 候选类型猜测, 归一化, 确保词库 = 取属性(
    "分词", "分句", "分词", "候选类型猜测", "归一化", "确保词库"
)
内存库存, 批量落盘, 是否需要试卷 = 取属性(
    "库存落盘", "内存库存", "批量落盘", "是否需要试卷"
)

logger = logging.getLogger("v2.knowledge.node07a.enumerate")


async def 枚举文档(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    *,
    库存: Any | None = None,
    立即落盘: bool = True,
) -> dict[str, Any]:
    """对单篇文档融合页做主体枚举。

    库存=None 时内部新建；批跑可复用同一 库存，最后统一批量落盘。
    """
    t0 = perf_counter()
    stats: dict[str, Any] = {
        "document_id": int(document_id),
        "owner_id": int(owner_id),
        "status": "ok",
        "pages": 0,
        "sentences": 0,
        "tokens_written": 0,
        "occurrences_written": 0,
        "combos_written": 0,
        "exam_items_written": 0,
        "unique_tokens_touched": 0,
        "lexicon_size": 0,
        "errors": [],
    }

    # 词典从数据库载入（entity_dictionary / terms / 已沉淀 subject_tokens）
    lexicon = await 确保词库(db, int(owner_id))
    stats["lexicon_size"] = len(lexicon or {})

    r = await db.execute(
        select(KbPageFusion)
        .where(
            KbPageFusion.document_id == int(document_id),
            KbPageFusion.owner_id == int(owner_id),
            KbPageFusion.fused_text != "",
        )
        .order_by(KbPageFusion.page)
    )
    fusions = r.scalars().all()
    if not fusions:
        stats["status"] = "skipped"
        stats["errors"].append("no_fused_pages")
        stats["duration_ms"] = round((perf_counter() - t0) * 1000)
        return stats

    local = 库存 if 库存 is not None else 内存库存(owner_id=int(owner_id))
    local.新文档()
    before_tokens = len(local.词条)
    before_occ = len(local.出现)
    before_combo = len(local.组合)
    before_exam = len(local.试卷)

    for pf in fusions:
        page = int(pf.page or 0)
        stats["pages"] += 1
        body = pf.fused_text or ""
        for sentence in 分句(body):
            stats["sentences"] += 1
            tokens = 分词(sentence, owner_id=int(owner_id))
            if not tokens:
                continue
            typed = 0
            norms: list[str] = []
            for idx, tok in enumerate(tokens):
                types = 候选类型猜测(tok, owner_id=int(owner_id))
                if types:
                    typed += 1
                norm = local.记词(tok, types)
                norms.append(norm)
                left = tokens[idx - 1] if idx > 0 else None
                right = tokens[idx + 1] if idx + 1 < len(tokens) else None
                if local.记出现(
                    document_id=int(document_id),
                    page=page,
                    sentence=sentence,
                    token_norm=norm,
                    left_token=left,
                    right_token=right,
                    position=idx,
                ):
                    stats["occurrences_written"] += 1

            for i in range(len(tokens) - 1):
                if local.记组合(tokens[i], tokens[i + 1]):
                    stats["combos_written"] += 1

            typed_ratio = typed / max(len(tokens), 1)
            reason = 是否需要试卷(sentence, tokens, typed_ratio)
            if reason and local.记试卷(
                document_id=int(document_id),
                page=page,
                sentence=sentence,
                tokens=tokens,
                reason=reason,
            ):
                stats["exam_items_written"] += 1

    stats["unique_tokens_touched"] = max(0, len(local.词条) - before_tokens)
    stats["tokens_written"] = stats["unique_tokens_touched"]
    # 出现/组合/试卷若复用库存，上面已按增量计数；此处校正为真实增量
    stats["occurrences_written"] = max(0, len(local.出现) - before_occ)
    stats["combos_written"] = max(0, len(local.组合) - before_combo)
    stats["exam_items_written"] = max(0, len(local.试卷) - before_exam)

    if 立即落盘 and 库存 is None:
        flush = await 批量落盘(db, local)
        stats["flush"] = flush

    stats["duration_ms"] = round((perf_counter() - t0) * 1000)
    logger.info(
        "07A 文档%s: pages=%s sentences=%s tokens=%s occ=%s combos=%s exam=%s ms=%s",
        document_id,
        stats["pages"],
        stats["sentences"],
        stats["unique_tokens_touched"],
        stats["occurrences_written"],
        stats["combos_written"],
        stats["exam_items_written"],
        stats["duration_ms"],
    )
    return stats


async def 枚举(
    db: AsyncSession,
    owner_id: int,
    *,
    document_ids: Iterable[int] | None = None,
    limit: int | None = 50,
) -> dict[str, Any]:
    """存量批跑：对 owner 下有融合正文的文档做枚举。内存累计后一次批量落库。"""
    t0 = perf_counter()
    out: dict[str, Any] = {
        "owner_id": int(owner_id),
        "status": "ok",
        "documents": 0,
        "ok": 0,
        "skipped": 0,
        "failed": 0,
        "totals": {
            "tokens_written": 0,
            "occurrences_written": 0,
            "combos_written": 0,
            "exam_items_written": 0,
            "unique_tokens_touched": 0,
        },
        "items": [],
        "errors": [],
        "flush": {},
    }

    if document_ids:
        ids = [int(x) for x in document_ids]
    else:
        q = (
            select(KbDocument.id)
            .where(
                KbDocument.owner_id == int(owner_id),
                KbDocument.deleted.is_(False),
            )
            .order_by(KbDocument.id.asc())
        )
        if limit:
            q = q.limit(int(limit))
        ids = [int(x) for x in (await db.execute(q)).scalars().all()]
        if ids:
            fr = await db.execute(
                select(KbPageFusion.document_id)
                .where(
                    KbPageFusion.owner_id == int(owner_id),
                    KbPageFusion.document_id.in_(ids),
                    KbPageFusion.fused_text != "",
                )
                .distinct()
            )
            ids = [int(x) for x in fr.scalars().all()]

    # 词库只加载一次
    await 确保词库(db, int(owner_id))
    库存 = 内存库存(owner_id=int(owner_id))

    for doc_id in ids:
        out["documents"] += 1
        try:
            one = await 枚举文档(db, doc_id, int(owner_id), 库存=库存, 立即落盘=False)
            out["items"].append(one)
            if one.get("status") == "ok":
                out["ok"] += 1
            else:
                out["skipped"] += 1
            for k in out["totals"]:
                out["totals"][k] += int(one.get(k, 0) or 0)
        except Exception as exc:  # noqa: BLE001
            out["failed"] += 1
            out["errors"].append({"document_id": doc_id, "error": str(exc)[:200]})
            logger.warning("07A 文档%s 失败: %s", doc_id, exc)
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass

    # 统一批量落库（一次 commit）
    try:
        out["flush"] = await 批量落盘(db, 库存)
    except Exception as exc:  # noqa: BLE001
        out["status"] = "flush_failed"
        out["errors"].append({"stage": "flush", "error": str(exc)[:300]})
        logger.exception("07A 批量落盘失败 owner=%s: %s", owner_id, exc)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass

    out["duration_ms"] = round((perf_counter() - t0) * 1000)
    out["memory"] = {
        "tokens": len(库存.词条),
        "occurrences": len(库存.出现),
        "combos": len(库存.组合),
        "exams": len(库存.试卷),
    }
    logger.info(
        "07A 批跑 owner=%s docs=%s ok=%s failed=%s mem_tokens=%s flush=%s ms=%s",
        owner_id,
        out["documents"],
        out["ok"],
        out["failed"],
        len(库存.词条),
        out.get("flush"),
        out["duration_ms"],
    )
    return out


# 英文兼容出口（API/工具名侧可继续用）
async def enumerate_document(db: AsyncSession, document_id: int, owner_id: int) -> dict[str, Any]:
    return await 枚举文档(db, document_id, owner_id)
