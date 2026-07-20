# -*- coding: utf-8 -*-
"""节点④ 唯一对外接口。

函数：描述图像(db, document_id, owner_id, page, force=False) -> dict
- 拉页面图 → VLM认字(round2) + VLM描述(round3) → 写 kb_raw_data
- 幂等：round2/round3 已 status=done 且 content 非空则跳过（force=True 强制重跑）
- 不改 pipeline_stages；本模块是补充包装，现有 raw_ocr/raw_vision 链不动

入参：db, document_id, owner_id, page
出参：{ocr, vision, skipped, status, ...}
依赖：页面渲染 / VLM认字 / VLM描述 / KbDocument.file_id
"""
from __future__ import annotations

import hashlib
import logging
from time import perf_counter
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import KbDocument, KbRawData
from .VLM描述 import 描述 as VLM描述
from .VLM认字 import 认字 as VLM认字
from .页面渲染 import 获取页面图片

logger = logging.getLogger("v2.knowledge.node04")


def _hash(content: str) -> str:
    return hashlib.md5((content or "").encode("utf-8", errors="replace")).hexdigest()


async def _查已完成(
    db: AsyncSession,
    document_id: int,
    page: int,
    round_no: int,
) -> KbRawData | None:
    r = await db.execute(
        select(KbRawData)
        .where(
            KbRawData.document_id == int(document_id),
            KbRawData.page == int(page),
            KbRawData.round == int(round_no),
            KbRawData.status == "done",
            KbRawData.content != "",
        )
        .order_by(KbRawData.id.desc())
        .limit(1)
    )
    return r.scalar_one_or_none()


async def _写raw(
    db: AsyncSession,
    *,
    document_id: int,
    file_id: int,
    owner_id: int,
    page: int,
    round_no: int,
    source_type: str,
    content: str,
    model_used: str,
    confidence: float,
    metadata: dict,
    status: str,
    error_message: str | None,
    duration_ms: int,
) -> int:
    """覆盖写该页该 round（先删旧再插，幂等重跑用）。"""
    await db.execute(
        sa_delete(KbRawData).where(
            KbRawData.document_id == int(document_id),
            KbRawData.page == int(page),
            KbRawData.round == int(round_no),
        )
    )
    rec = KbRawData(
        document_id=int(document_id),
        file_id=int(file_id),
        owner_id=int(owner_id),
        page=int(page),
        round=int(round_no),
        source_type=source_type,
        content=content or "",
        model_used=model_used,
        confidence=confidence,
        content_hash=_hash(content or ""),
        metadata_json=metadata or {},
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(rec)
    await db.flush()
    return int(rec.id)


async def 描述图像(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    page: int = 1,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """单页：OCR 认字 + 视觉描述，写入 kb_raw_data round2/round3。"""
    t0 = perf_counter()
    统计: dict[str, Any] = {
        "document_id": int(document_id),
        "owner_id": int(owner_id),
        "page": int(page),
        "force": force,
        "status": "ok",
        "ocr": {},
        "vision": {},
        "skipped": {"ocr": False, "vision": False},
    }

    doc = await db.scalar(
        select(KbDocument).where(
            KbDocument.id == int(document_id),
            KbDocument.owner_id == int(owner_id),
        )
    )
    if doc is None:
        统计["status"] = "error"
        统计["error"] = "document_not_found"
        return 统计
    file_id = int(getattr(doc, "file_id", 0) or 0)

    # 幂等检查
    if not force:
        old2 = await _查已完成(db, document_id, page, 2)
        old3 = await _查已完成(db, document_id, page, 3)
        if old2 is not None and old3 is not None:
            统计["skipped"] = {"ocr": True, "vision": True}
            统计["status"] = "already_done"
            统计["ocr"] = {
                "content_head": (old2.content or "")[:100],
                "chars": len(old2.content or ""),
                "status": old2.status,
                "model_used": old2.model_used,
                "skipped": True,
            }
            统计["vision"] = {
                "content_head": (old3.content or "")[:200],
                "chars": len(old3.content or ""),
                "status": old3.status,
                "model_used": old3.model_used,
                "skipped": True,
            }
            统计["timing_ms"] = round((perf_counter() - t0) * 1000)
            return 统计
        skip_ocr = old2 is not None
        skip_vision = old3 is not None
    else:
        skip_ocr = False
        skip_vision = False

    # 需要跑任一路时才取图
    img_pack = None
    if not skip_ocr or not skip_vision:
        try:
            img_pack = await 获取页面图片(db, document_id, page, owner_id)
        except Exception as exc:  # noqa: BLE001
            统计["status"] = "error"
            统计["error"] = f"page_asset:{exc}"[:200]
            return 统计
        if img_pack is None:
            统计["status"] = "error"
            统计["error"] = "page_asset_missing"
            return 统计

    img_bytes = (img_pack or {}).get("img_bytes") or b""
    mime_type = (img_pack or {}).get("mime_type") or "image/jpeg"

    # OCR
    if skip_ocr:
        old2 = await _查已完成(db, document_id, page, 2)
        统计["skipped"]["ocr"] = True
        统计["ocr"] = {
            "content_head": ((old2.content if old2 else "") or "")[:100],
            "chars": len((old2.content if old2 else "") or ""),
            "status": old2.status if old2 else "skipped",
            "skipped": True,
        }
    else:
        try:
            ocr = await VLM认字(
                img_bytes,
                mime_type,
                document_id=document_id,
                page=page,
            )
            rid = await _写raw(
                db,
                document_id=document_id,
                file_id=file_id,
                owner_id=owner_id,
                page=page,
                round_no=2,
                source_type="ocr",
                content=ocr.get("content") or "",
                model_used=str(ocr.get("model_used") or "grok-4.5-vision"),
                confidence=0.85 if ocr.get("content") else 0.0,
                metadata=ocr.get("metadata") or {},
                status=str(ocr.get("status") or "degraded"),
                error_message=ocr.get("error"),
                duration_ms=int(ocr.get("duration_ms") or 0),
            )
            await db.commit()
            统计["ocr"] = {
                "raw_id": rid,
                "content_head": (ocr.get("content") or "")[:100],
                "content": ocr.get("content") or "",
                "chars": ocr.get("chars") or 0,
                "status": ocr.get("status"),
                "model_used": ocr.get("model_used"),
                "duration_ms": ocr.get("duration_ms"),
                "skipped": False,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("节点④ OCR 落库失败: %s", exc)
            统计["ocr"] = {"status": "error", "error": str(exc)[:200]}
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass

    # Vision
    if skip_vision:
        old3 = await _查已完成(db, document_id, page, 3)
        统计["skipped"]["vision"] = True
        统计["vision"] = {
            "content_head": ((old3.content if old3 else "") or "")[:200],
            "chars": len((old3.content if old3 else "") or ""),
            "status": old3.status if old3 else "skipped",
            "skipped": True,
        }
    else:
        try:
            vis = await VLM描述(
                img_bytes,
                mime_type,
                document_id=document_id,
                page=page,
            )
            rid = await _写raw(
                db,
                document_id=document_id,
                file_id=file_id,
                owner_id=owner_id,
                page=page,
                round_no=3,
                source_type="vision",
                content=vis.get("content") or "",
                model_used=str(vis.get("model_used") or "grok-4.5-vision"),
                confidence=0.80 if vis.get("content") else 0.0,
                metadata=vis.get("metadata") or {},
                status=str(vis.get("status") or "degraded"),
                error_message=vis.get("error"),
                duration_ms=int(vis.get("duration_ms") or 0),
            )
            await db.commit()
            统计["vision"] = {
                "raw_id": rid,
                "content_head": (vis.get("content") or "")[:200],
                "content": vis.get("content") or "",
                "chars": vis.get("chars") or 0,
                "status": vis.get("status"),
                "model_used": vis.get("model_used"),
                "duration_ms": vis.get("duration_ms"),
                "skipped": False,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("节点④ 描述落库失败: %s", exc)
            统计["vision"] = {"status": "error", "error": str(exc)[:200]}
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass

    ocr_ok = 统计.get("ocr", {}).get("status") in ("done",) or 统计["skipped"]["ocr"]
    vis_ok = 统计.get("vision", {}).get("status") in ("done",) or 统计["skipped"]["vision"]
    if 统计["skipped"]["ocr"] and 统计["skipped"]["vision"]:
        统计["status"] = "already_done"
    elif ocr_ok and vis_ok:
        统计["status"] = "ok"
    elif not ocr_ok and not vis_ok:
        统计["status"] = "failed"
    else:
        统计["status"] = "degraded"

    统计["timing_ms"] = round((perf_counter() - t0) * 1000)
    logger.info(
        "节点④ 文档%s 页%s: status=%s ocr_skip=%s vis_skip=%s",
        document_id,
        page,
        统计["status"],
        统计["skipped"]["ocr"],
        统计["skipped"]["vision"],
    )
    return 统计
