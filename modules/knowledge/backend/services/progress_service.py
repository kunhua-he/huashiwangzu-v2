"""知识库分析进度聚合服务。

从各层真实表实时算出每阶段细颗粒进度(截图 3/10 这种),供前端轮询。
关键用途:前端关闭重开后调本接口握手 → 100% 同步后端真实进度。
进度全部从落库数据现算,不依赖内存,多 worker/重启都一致。
"""
import logging

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    KbDocument,
    KbDocumentProfile,
    KbFileRelation,
    KbGovernanceCandidate,
    KbPageFusion,
    KbPipelineRun,
    KbRawData,
)
from .source_file_state import accessible_document_clause, get_source_file_availability

logger = logging.getLogger("v2.knowledge").getChild("progress")


def _stage(key: str, label: str, done: int, total: int, count: int | None = None) -> dict:
    """构造单阶段进度。status: done(满)/running(有进展未满)/pending(未开始)。"""
    total = max(total, 0)
    done = min(done, total) if total else done
    if total > 0 and done >= total:
        status = "done"
    elif done > 0:
        status = "running"
    else:
        status = "pending"
    percent = round(done / total * 100) if total > 0 else (100 if status == "done" else 0)
    item = {"key": key, "label": label, "done": done, "total": total,
            "percent": percent, "status": status}
    if count is not None:
        item["count"] = count
    return item


def _stage_with_status(key: str, label: str, done: int, total: int, status: str, count: int | None = None) -> dict:
    item = _stage(key, label, done, total, count=count)
    normalized = status or item["status"]
    if normalized in {"done", "running", "pending", "failed", "degraded", "paused", "source_unavailable"}:
        item["status"] = normalized
        if normalized == "done":
            item["done"] = max(done, total, 1)
            item["percent"] = 100
    return item


async def get_document_progress(db: AsyncSession, document_id: int, owner_id: int) -> dict:
    """聚合单文档全链路细颗粒进度。"""
    dr = await db.execute(
        select(KbDocument).where(
            KbDocument.id == document_id,
            accessible_document_clause(owner_id),
            KbDocument.deleted.is_(False),
        )
    )
    doc = dr.scalar_one_or_none()
    if not doc:
        from app.core.exceptions import NotFound
        raise NotFound("Document not found")

    total_pages = doc.total_pages or 0
    source = await get_source_file_availability(db, int(doc.file_id or 0))

    # 原始三轮:按 round 统计已落库的不同页数(逐页 commit 后实时增长)
    rr = await db.execute(
        select(KbRawData.round, func.count(distinct(KbRawData.page)))
        .where(KbRawData.document_id == document_id)
        .group_by(KbRawData.round)
    )
    round_done = {rd: cnt for rd, cnt in rr.all()}

    # 第4层融合:已 done 的页
    fusion_done = (await db.execute(
        select(func.count(KbPageFusion.id)).where(
            KbPageFusion.document_id == document_id,
            KbPageFusion.fusion_status == "done",
        )
    )).scalar() or 0

    # 第5层画像
    profile_done = (await db.execute(
        select(func.count(KbDocumentProfile.id)).where(
            KbDocumentProfile.document_id == document_id
        )
    )).scalar() or 0

    # 第6层图谱:本文档抽出的实体数(治理候选 doc 级归属)
    entity_count = (await db.execute(
        select(func.count(KbGovernanceCandidate.id)).where(
            KbGovernanceCandidate.document_id == document_id
        )
    )).scalar() or 0

    # 第7层跨文件关联:本文档参与的关联边
    relation_count = (await db.execute(
        select(func.count(KbFileRelation.id)).where(
            (KbFileRelation.source_document_id == document_id)
            | (KbFileRelation.target_document_id == document_id)
        )
    )).scalar() or 0

    latest_run = (await db.execute(
        select(KbPipelineRun)
        .where(KbPipelineRun.document_id == document_id, KbPipelineRun.owner_id == doc.owner_id)
        .order_by(KbPipelineRun.id.desc())
        .limit(1)
    )).scalar_one_or_none()
    paused = latest_run is not None and latest_run.status == "paused"

    tp = total_pages
    raw_status = doc.raw_status or "pending"
    fusion_status = doc.fusion_status or "pending"
    profile_status = getattr(doc, "profile_status", "pending") or "pending"
    graph_status = getattr(doc, "graph_status", "pending") or "pending"
    relation_status = getattr(doc, "relation_status", "pending") or "pending"
    effective_profile_status = "done" if profile_status == "pending" and profile_done > 0 else profile_status
    effective_graph_status = "done" if graph_status == "pending" and entity_count > 0 else graph_status
    effective_relation_status = "done" if relation_status == "pending" and relation_count > 0 else relation_status
    stages = [
        _stage("text", "提取文字", round_done.get(1, 0), tp),
        _stage("ocr", "识别截图", round_done.get(2, 0), tp),
        _stage("vision", "理解版面", round_done.get(3, 0), tp),
        _stage_with_status("fusion", "交叉印证", fusion_done, tp, fusion_status),
        _stage_with_status("profile", "提炼画像", profile_done, 1, effective_profile_status, count=profile_done),
        _stage_with_status("graph", "构建图谱", 1 if entity_count > 0 else 0, 1, effective_graph_status, count=entity_count),
        _stage_with_status("relation", "关联织网", 1 if relation_count > 0 else 0, 1, effective_relation_status, count=relation_count),
    ]

    # 整体状态:raw_status / fusion_status 为权威态;细分阶段算百分比
    if not source.available:
        overall_status = "source_unavailable"
    elif paused:
        overall_status = "paused"
    elif any(s == "failed" for s in (raw_status, fusion_status, effective_profile_status, effective_graph_status, effective_relation_status)):
        overall_status = "failed"
    elif any(s == "degraded" for s in (raw_status, fusion_status, effective_profile_status, effective_graph_status, effective_relation_status)):
        overall_status = "degraded"
    elif all(s == "done" for s in (raw_status, fusion_status, effective_profile_status, effective_graph_status, effective_relation_status)):
        overall_status = "done"
    elif all(s == "pending" for s in (raw_status, fusion_status, effective_profile_status, effective_graph_status, effective_relation_status)):
        overall_status = "pending"
    else:
        overall_status = "running"

    # 当前正在跑的阶段(第一个非 done 的页级阶段)
    current = "源文件不可用" if not source.available else next((s["label"] for s in stages if s["status"] != "done"), "已完成")
    if paused:
        current = "模型降级后已暂停"

    # 整体百分比:页级阶段(前4个)平均
    page_stages = [s for s in stages if s["key"] in ("text", "ocr", "vision", "fusion")]
    overall_percent = round(sum(s["percent"] for s in page_stages) / len(page_stages)) if page_stages else 0
    if overall_status == "done":
        overall_percent = 100

    return {
        "document_id": document_id,
        "filename": doc.filename,
        "total_pages": total_pages,
        "overall_status": overall_status,
        "quality_status": "degraded" if overall_status in {"degraded", "paused"} else ("unavailable" if overall_status == "source_unavailable" else "ok"),
        "overall_percent": overall_percent,
        "current_stage": current,
        "source_available": source.available,
        "source_state": source.reason or "available",
        "stages": stages,
    }


async def list_documents_progress(db: AsyncSession, owner_id: int, document_ids: list[int]) -> dict:
    """批量查多个文档进度(前端握手:一次拿回所有在处理文档的真实进度)。"""
    result = {}
    for did in document_ids:
        try:
            result[did] = await get_document_progress(db, did, owner_id)
        except Exception as e:
            logger.warning("Progress for doc_id=%d failed: %s", did, e)
    return result
