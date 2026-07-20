# -*- coding: utf-8 -*-
"""节点⑥ 唯一对外接口。

函数：fuse_document(db, document_id, owner_id, force=False, 启用LLM补充=False) -> dict
pipeline_stages/fusion.py 只调本接口。

流程（单页）：
1. 读三路 raw
2. 文本层优先？→ fused_text=round1（可选 LLM 补充追加）
3. 否则 → LLM 兜底（图片/无文本）
4. 写 kb_page_fusions；文档级再 index_fusions_to_chunks

幂等：force=False 且 fusion_status=done 且 fused_text 非空 → 跳过。
失败不拖垮：单页异常只记该页。
"""
from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from typing import Any

from app.database import AsyncSessionLocal
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument, KbPageFusion, KbRawData
from ..fusion_service import (
    _detect_simple_conflicts,
    classify_fusion_status,
    index_fusions_to_chunks,
)
from ..model_routing import resolve_knowledge_concurrency
from ..parsing_service import IMAGE_FORMATS
from .LLM兜底 import LLM兜底融合
from .LLM补充 import 补充新信息, 追加到文本
from .文本层优先 import 文本层优先融合

logger = logging.getLogger("v2.knowledge.node06")

页并发默认 = 6


def _是图片扩展(extension: str | None) -> bool:
    return (extension or "").lower().lstrip(".") in IMAGE_FORMATS


async def _融合单页(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    page: int,
    *,
    is_image: bool,
    启用LLM补充: bool,
) -> dict[str, Any]:
    """单页融合核心。"""
    started = perf_counter()
    r = await db.execute(
        select(KbRawData)
        .where(KbRawData.document_id == document_id, KbRawData.page == page)
        .order_by(KbRawData.round)
    )
    raw_records = r.scalars().all()
    round_texts: dict[int, str] = {}
    evidence_ids: list[int] = []
    for rec in raw_records:
        round_texts[int(rec.round)] = rec.content or ""
        evidence_ids.append(int(rec.id))

    if not round_texts:
        await db.commit()
        return {
            "page": page,
            "fused_text": "",
            "confidence": 0.0,
            "status": "degraded",
            "strategy": "no_raw",
            "llm_called": False,
            "is_text_dominant": False,
            "diagnostics": {"reason": "no_raw_data"},
        }
    await db.commit()

    simple_conflicts = _detect_simple_conflicts(
        {k: v for k, v in round_texts.items() if not (is_image and k == 1)}
    )
    image_tech = (round_texts.get(1) or "").strip() if is_image else ""

    text_result = 文本层优先融合(round_texts, is_image=is_image)
    llm_called = False
    supplement_meta: dict[str, Any] = {}

    if text_result is not None:
        fused_text = text_result["fused_text"]
        strategy = "text_dominant"
        confidence = float(text_result["confidence"])
        page_summary = text_result.get("page_summary") or fused_text[:120]
        page_title = text_result.get("page_title")
        entities = text_result.get("entities") or []
        attributes = dict(text_result.get("attributes") or {})
        tags = text_result.get("tags") or []
        conflicts = list(text_result.get("conflicts") or []) + simple_conflicts
        is_text_dominant = True
        model_diagnostics: dict = {}
        model_degraded = False

        if 启用LLM补充:
            sup = await 补充新信息(
                round_texts.get(1, ""),
                round_texts.get(2, ""),
                round_texts.get(3, ""),
                document_id=document_id,
                page=page,
            )
            supplement_meta = {
                "supplement_len": len(sup.get("supplement") or ""),
                "supplement_skipped": sup.get("skipped"),
                "supplement_error": sup.get("error"),
            }
            if sup.get("llm_called"):
                llm_called = True
            if sup.get("supplement"):
                fused_text = 追加到文本(fused_text, sup["supplement"])
                page_summary = fused_text[:120]
                attributes["有LLM补充"] = True
                strategy = "text_dominant_plus_supplement"
            model_diagnostics = sup.get("model_diagnostics") or {}
            model_degraded = bool(sup.get("model_degraded"))
    else:
        fusion_result = await LLM兜底融合(
            round_texts,
            is_image=is_image or not (round_texts.get(1) or "").strip(),
            document_id=document_id,
            page=page,
        )
        llm_called = bool(fusion_result.get("llm_called", True))
        fused_text = (fusion_result.get("fused_text") or "").strip()
        strategy = str(fusion_result.get("strategy") or "llm_fallback")
        llm_conf = float(fusion_result.get("confidence") or 0.7)
        # 启发式权重轻量保留
        from ..fusion_service import _compute_confidence

        heur = _compute_confidence(round_texts, simple_conflicts)
        confidence = round(llm_conf * 0.6 + heur * 0.4, 2)
        page_summary = fusion_result.get("page_summary") or fused_text[:120]
        page_title = fusion_result.get("page_title")
        entities = fusion_result.get("entities") or []
        attributes = dict(fusion_result.get("attributes") or {})
        tags = fusion_result.get("tags") or []
        conflicts = list(fusion_result.get("conflicts") or []) + simple_conflicts
        is_text_dominant = False
        model_diagnostics = fusion_result.get("model_diagnostics") or {}
        model_degraded = bool(fusion_result.get("model_degraded"))

    if image_tech:
        attributes["图像技术属性"] = image_tech

    page_status = "done" if fused_text else "degraded"
    duration_ms = round((perf_counter() - started) * 1000)
    diagnostics = {
        "raw_rounds": len(round_texts),
        "valid_raw_rounds": sum(1 for v in round_texts.values() if v and v.strip()),
        "conflict_count": len(conflicts),
        "strategy": strategy,
        "is_text_dominant": is_text_dominant,
        "llm_called": llm_called,
        "model_degraded": model_degraded,
        "model_diagnostics": model_diagnostics,
        "supplement": supplement_meta,
        "node": "06",
    }

    await db.execute(
        sa_delete(KbPageFusion).where(
            KbPageFusion.document_id == document_id,
            KbPageFusion.page == page,
        )
    )
    pf = KbPageFusion(
        document_id=document_id,
        owner_id=owner_id,
        page=page,
        fused_text=fused_text,
        page_summary=page_summary or "",
        page_title=page_title,
        body_json=entities,
        attributes_json=attributes,
        tags_json=tags,
        conflicts_json=conflicts,
        evidence_json=evidence_ids,
        source_version=1,
        fusion_version=2,  # 节点⑥ 文本层优先版本
        fusion_status=page_status,
        confidence=confidence,
        diagnostics_json=diagnostics,
        error_message=None if page_status == "done" else "empty_fused_text",
        duration_ms=duration_ms,
    )
    db.add(pf)
    await db.flush()

    return {
        "id": pf.id,
        "page": page,
        "fused_text": (pf.fused_text or "")[:500],
        "fused_text_full_len": len(pf.fused_text or ""),
        "page_summary": pf.page_summary,
        "confidence": confidence,
        "status": page_status,
        "strategy": strategy,
        "is_text_dominant": is_text_dominant,
        "llm_called": llm_called,
        "diagnostics": diagnostics,
        "duration_ms": duration_ms,
        "round1_len": len((round_texts.get(1) or "").strip()),
    }


async def fuse_document(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    force: bool = False,
    *,
    启用LLM补充: bool = False,
) -> dict[str, Any]:
    """文档级单页融合入口。force=True 强制重跑已 done 页。"""
    stage_started = perf_counter()
    df = await db.execute(select(KbDocument).where(KbDocument.id == document_id))
    doc = df.scalar_one_or_none()
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    total_pages = doc.total_pages or 1
    is_image = _是图片扩展(getattr(doc, "extension", None))
    doc.fusion_status = "running"
    await db.commit()

    done_pages: set[int] = set()
    if not force:
        r = await db.execute(
            select(KbPageFusion.page).where(
                KbPageFusion.document_id == document_id,
                KbPageFusion.fusion_status == "done",
                KbPageFusion.fused_text != "",
            )
        )
        done_pages = {int(row[0]) for row in r.all()}
        await db.commit()

    page_concurrency = resolve_knowledge_concurrency("page_fusion", 页并发默认)
    sem = asyncio.Semaphore(page_concurrency)

    async def _跑页(page: int) -> dict:
        if page in done_pages:
            return {
                "page": page,
                "skipped": True,
                "status": "done",
                "llm_called": False,
                "is_text_dominant": None,
            }
        async with sem:
            async with AsyncSessionLocal() as page_db:
                try:
                    result = await _融合单页(
                        page_db,
                        document_id,
                        owner_id,
                        page,
                        is_image=is_image,
                        启用LLM补充=启用LLM补充,
                    )
                    await page_db.commit()
                    return result
                except Exception as exc:  # noqa: BLE001
                    await page_db.rollback()
                    logger.error(
                        "节点⑥ 融合失败 doc=%s page=%s: %s", document_id, page, exc
                    )
                    return {"page": page, "error": str(exc)[:200], "llm_called": False}

    results = list(
        await asyncio.gather(*[_跑页(p) for p in range(1, total_pages + 1)])
    ) if total_pages > 0 else []

    # 索引融合层 chunk（复用 fusion_service）
    indexed = 0
    index_error = ""
    index_started = perf_counter()
    try:
        indexed = await index_fusions_to_chunks(db, document_id, owner_id)
    except Exception as exc:  # noqa: BLE001
        index_error = str(exc)[:200]
        logger.error("节点⑥ 索引失败 doc=%s: %s", document_id, exc)
    index_ms = round((perf_counter() - index_started) * 1000)

    fusion_rows = await db.execute(
        select(KbPageFusion.fused_text).where(KbPageFusion.document_id == document_id)
    )
    valid_pages = sum(1 for (t,) in fusion_rows.all() if t and str(t).strip())
    empty_pages = max(total_pages - valid_pages, 0)
    error_pages = sum(1 for item in results if item.get("error"))

    text_dominant_pages = sum(1 for item in results if item.get("is_text_dominant") is True)
    llm_pages = sum(1 for item in results if item.get("llm_called"))
    skipped_pages = sorted(
        int(item["page"]) for item in results if item.get("skipped") and item.get("page")
    )
    # 本轮实际处理的页（非 skip）
    processed = [item for item in results if not item.get("skipped")]
    processed_n = len(processed) or 1
    # LLM 节省率：有文本主导且未调 LLM 的页 / 处理页
    saved = sum(
        1
        for item in processed
        if item.get("is_text_dominant") and not item.get("llm_called")
    )
    llm_save_ratio = round(saved / processed_n, 4) if processed else 0.0

    await db.refresh(doc)
    doc.fusion_status = classify_fusion_status(
        total_pages=total_pages,
        valid_pages=valid_pages,
        error_pages=error_pages,
        index_error=index_error,
    )
    await db.commit()

    stats = {
        "document_id": document_id,
        "total_pages": total_pages,
        "pages_fused": valid_pages,
        "valid_pages": valid_pages,
        "empty_pages": empty_pages,
        "error_pages": error_pages,
        "indexed_chunks": indexed,
        "index_error": index_error,
        "status": doc.fusion_status,
        "is_image": is_image,
        "text_dominant_pages": text_dominant_pages,
        "llm_called_pages": llm_pages,
        "llm_save_ratio": llm_save_ratio,
        "llm_save_percent": f"{llm_save_ratio * 100:.1f}%",
        "force": force,
        "启用LLM补充": 启用LLM补充,
        "timing": {
            "stage_wall_ms": round((perf_counter() - stage_started) * 1000),
            "index_ms": index_ms,
            "page_concurrency": page_concurrency,
            "skipped_pages": skipped_pages,
            "execution_mode": "parallel_pages_node06",
        },
        "results": results,
    }
    logger.info(
        "节点⑥ 文档%s: status=%s text_dom=%s llm=%s save=%s",
        document_id,
        doc.fusion_status,
        text_dominant_pages,
        llm_pages,
        stats["llm_save_percent"],
    )
    return stats


async def 融合文档(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    force: bool = False,
    **kw: Any,
) -> dict[str, Any]:
    """中文别名。"""
    return await fuse_document(db, document_id, owner_id, force=force, **kw)
