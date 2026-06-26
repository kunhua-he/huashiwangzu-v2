"""知识库全链路管道（后台任务 kb_pipeline）。
	
按 采集→融合→画像→图谱→关联 顺序串行，每步落状态。
"""
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.task_worker import register_task_handler

from ..models import KbDocument
from .raw_collection_service import collect_raw_data
from .fusion_service import fuse_all_pages
from .profile_service import generate_document_profile
from .entity_service import process_document_entities_from_fusions
from .relation_service import compute_file_relations

logger = logging.getLogger("v2.knowledge").getChild("pipeline")


async def _run_pipeline(
    db: AsyncSession,
    document_id: int,
    owner_id: int,
    file_id: int,
    user_id: int,
    force_raw: bool = False,
    force_fusion: bool = False,
) -> dict:
    """按顺序执行全链路，每步完成后 commit 状态。

    返回每步结果汇总。
    """
    steps: dict[str, dict] = {}
    pipeline_started = time.perf_counter()

    # 第1步：原始采集
    t0 = time.perf_counter()
    logger.info("Pipeline step 1/5: raw collection doc_id=%d", document_id)
    if doc := (await db.execute(select(KbDocument).where(KbDocument.id == document_id))).scalar_one_or_none():
        if doc.raw_status != "done" or force_raw:
            try:
                steps["raw"] = await collect_raw_data(db, document_id, owner_id, file_id, user_id)
                await db.commit()
                steps["raw"]["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                logger.info("Pipeline raw collection done: %d rounds (%.0fms)", len(steps["raw"].get("rounds", [])), steps["raw"]["elapsed_ms"])
            except Exception as e:
                steps["raw"] = {"error": str(e), "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
                logger.error("Pipeline raw collection failed after %.0fms: %s", steps["raw"]["elapsed_ms"], e)
        else:
            steps["raw"] = {"status": "skipped", "reason": "already done", "elapsed_ms": 0}
    else:
        return {"error": f"Document {document_id} not found at step 1"}

    # Y3/Y6: 前步失败则短路，不继续跑后续步骤
    raw_step = steps.get("raw", {})
    if "error" in raw_step or raw_step.get("status") in ("failed", "aborted"):
        logger.error("Pipeline aborted after step 1 (raw collection %s) for doc_id=%d", raw_step.get("status", "error"), document_id)
        try:
            doc.raw_status = "failed"
            await db.commit()
        except Exception:
            pass
        return {"document_id": document_id, "status": "failed", "steps": steps}

    # 第2步：融合 — 重新查文档（防步骤间被删）
    doc = (await db.execute(select(KbDocument).where(KbDocument.id == document_id))).scalar_one_or_none()
    if not doc:
        logger.error("Document %d was deleted before fusion step, aborting pipeline", document_id)
        return {"document_id": document_id, "status": "aborted", "reason": "document deleted before fusion", "steps": steps}
    t0 = time.perf_counter()
    logger.info("Pipeline step 2/5: fusion doc_id=%d", document_id)
    if doc.fusion_status != "done" or force_fusion:
        try:
            steps["fusion"] = await fuse_all_pages(db, document_id, owner_id)
            steps["fusion"]["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            await db.commit()
        except Exception as e:
            steps["fusion"] = {"error": str(e), "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
            logger.error("Pipeline fusion failed after %.0fms: %s", steps["fusion"]["elapsed_ms"], e)
    else:
        steps["fusion"] = {"status": "skipped", "reason": "already done", "elapsed_ms": 0}
    await db.refresh(doc)

    # Y6: 融合失败则短路
    if "error" in steps.get("fusion", {}):
        logger.error("Pipeline aborted after step 2 (fusion failed) for doc_id=%d", document_id)
        return {"document_id": document_id, "status": "failed", "steps": steps}

    # 第3步：画像 — 重新查文档
    doc = (await db.execute(select(KbDocument).where(KbDocument.id == document_id))).scalar_one_or_none()
    if not doc:
        logger.error("Document %d was deleted before profile step, aborting pipeline", document_id)
        return {"document_id": document_id, "status": "aborted", "reason": "document deleted before profile", "steps": steps}
    t0 = time.perf_counter()
    logger.info("Pipeline step 3/5: profile doc_id=%d", document_id)
    try:
        steps["profile"] = await generate_document_profile(db, document_id, owner_id)
        steps["profile"]["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        await db.commit()
    except Exception as e:
        steps["profile"] = {"error": str(e), "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
        logger.error("Pipeline profile failed after %.0fms: %s", steps["profile"]["elapsed_ms"], e)

    # 第4步：图谱 — 重新查文档
    doc = (await db.execute(select(KbDocument).where(KbDocument.id == document_id))).scalar_one_or_none()
    if not doc:
        logger.error("Document %d was deleted before graph step, aborting pipeline", document_id)
        return {"document_id": document_id, "status": "aborted", "reason": "document deleted before graph", "steps": steps}
    t0 = time.perf_counter()
    logger.info("Pipeline step 4/5: graph doc_id=%d", document_id)
    try:
        steps["graph"] = await process_document_entities_from_fusions(db, document_id, owner_id)
        steps["graph"]["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        await db.commit()
    except Exception as e:
        steps["graph"] = {"error": str(e), "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
        logger.error("Pipeline graph failed after %.0fms: %s", steps["graph"]["elapsed_ms"], e)

    # 第5步：跨文件关联 — 重新查文档
    doc = (await db.execute(select(KbDocument).where(KbDocument.id == document_id))).scalar_one_or_none()
    if not doc:
        logger.error("Document %d was deleted before relations step, aborting pipeline", document_id)
        return {"document_id": document_id, "status": "aborted", "reason": "document deleted before relations", "steps": steps}
    t0 = time.perf_counter()
    logger.info("Pipeline step 5/5: relations doc_id=%d", document_id)
    try:
        steps["relations"] = await compute_file_relations(db, document_id, owner_id)
        steps["relations"]["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        await db.commit()
    except Exception as e:
        steps["relations"] = {"error": str(e), "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)}
        logger.error("Pipeline relations failed after %.0fms: %s", steps["relations"]["elapsed_ms"], e)

    # 汇总结果
    has_errors = any("error" in s for s in steps.values())
    status = "done_with_errors" if has_errors else "done"
    total_elapsed = round((time.perf_counter() - pipeline_started) * 1000, 1)
    logger.info("Pipeline completed doc_id=%d status=%s total_ms=%.0f", document_id, status, total_elapsed)
    return {"document_id": document_id, "status": status, "steps": steps, "total_elapsed_ms": total_elapsed}


# ── 框架任务 handler ────────────────────────────────


async def _pipeline_handler(params: dict) -> dict:
    """框架后台任务 handler：处理 kb_pipeline 任务。

    参数: {"document_id": int, "user_id": int}
    """
    document_id = int(params.get("document_id", 0))
    user_id = int(params.get("user_id", 0)) or 1
    if document_id <= 0:
        return {"error": "document_id required", "status": "failed"}

    async with AsyncSessionLocal() as db:
        df = await db.execute(select(KbDocument).where(KbDocument.id == document_id))
        doc = df.scalar_one_or_none()
        if not doc:
            return {"error": f"Document {document_id} not found", "status": "failed"}

        try:
            result = await _run_pipeline(
                db, document_id, doc.owner_id, doc.file_id, user_id,
                force_raw=params.get("force_raw", False),
                force_fusion=params.get("force_fusion", False),
            )
            return {"status": "done", **result}
        except Exception as e:
            logger.error("Pipeline handler failed for document_id=%d: %s", document_id, e)
            return {"error": str(e), "status": "failed"}


register_task_handler("kb_pipeline", _pipeline_handler)
