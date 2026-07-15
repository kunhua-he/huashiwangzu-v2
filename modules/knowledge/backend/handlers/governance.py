"""Governance endpoints (pipeline-debt, reconcile, lifecycle, rerun, entity governance)."""
import logging
from typing import Literal

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.governance_service import (
    approve_candidate,
    calibrate_extraction,
    get_pending_count,
    list_governance_candidates,
    merge_entities,
    reject_candidate,
)
from ..services.lifecycle_debt_service import (
    archive_source_unavailable_documents,
    audit_lifecycle_debt,
)
from ..services.pipeline_debt_api import (
    merge_category_params,
    parse_category_limits_query,
)
from ..services.pipeline_debt_service import (
    apply_pipeline_lifecycle_debt_action,
    classify_pipeline_lifecycle_debt,
    reconcile_pending_pipeline_queue,
)
from ..services.pipeline_reconcile_service import (
    apply_orphan_pipeline_run_reconcile,
    dry_run_orphan_pipeline_run_reconcile,
)
from ..services.rerun_planner_service import plan_pipeline_rerun
from ..services.retrieval_learning_service import reflect_retrieval_feedback

logger = logging.getLogger("v2.knowledge").getChild("handlers.governance")

sub_router = APIRouter()


class MergeEntitiesRequest(BaseModel):
    source_entity_ids: list[int]
    target_entity_id: int
    reason: str = ""


class CalibrateRequest(BaseModel):
    candidate_id: int
    new_name: str | None = None
    new_category: str | None = None


class PipelineDebtApplyRequest(BaseModel):
    action: Literal["archive_obsolete", "retry_live"]
    limit: int = Field(default=500, ge=1, le=5000)
    task_ids: list[int] = Field(default_factory=list)
    dry_run: bool = True
    category: str | None = None
    categories: list[str] = Field(default_factory=list)
    category_limits: dict[str, int] = Field(default_factory=dict)
    limit_each: int | None = Field(default=None, ge=1, le=5000)
    order: Literal["newest", "oldest"] = "newest"


class PipelineRunReconcileRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)
    run_ids: list[int] = Field(default_factory=list)
    dry_run: bool = True


class PendingPipelineQueueReconcileRequest(BaseModel):
    limit: int = Field(default=500, ge=1, le=5000)
    task_ids: list[int] = Field(default_factory=list)
    dry_run: bool = True
    category: str | None = None
    categories: list[str] = Field(default_factory=list)
    category_limits: dict[str, int] = Field(default_factory=dict)
    limit_each: int | None = Field(default=None, ge=1, le=5000)
    order: Literal["newest", "oldest"] = "oldest"


class LifecycleArchiveRequest(BaseModel):
    dry_run: bool = True
    limit: int = Field(default=100, ge=1, le=5000)
    all_owners: bool = False
    reason: Literal[
        "source_file_deleted",
        "source_file_missing",
        "source_storage_path_missing",
        "source_path_unsafe",
        "source_file_physical_missing",
        "source_unavailable",
    ] = "source_unavailable"
    confirm: str = ""
    audit_reason: str = ""


class RerunPlanRequest(BaseModel):
    document_id: int
    reason: Literal[
        "prompt_changed",
        "schema_changed",
        "model_changed",
        "source_changed",
        "vlm_preprocess_changed",
        "manual_failed_retry",
    ]
    stage: str | None = None


class RetrievalFeedbackReflectRequest(BaseModel):
    query_context_id: int = Field(..., gt=0)
    conversation_excerpt: str = Field(..., min_length=1, max_length=16000)


@sub_router.get("/governance/candidates")
async def api_governance_candidates(
    audit_status: str = Query(default="pending"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await list_governance_candidates(db, user.id, audit_status, page, page_size)
    return ApiResponse(data=result)


@sub_router.post("/governance/candidates/{candidate_id}/approve")
async def api_approve_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    ok = await approve_candidate(db, candidate_id, user.id)
    return ApiResponse(data={"ok": ok})


@sub_router.post("/governance/candidates/{candidate_id}/reject")
async def api_reject_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    ok = await reject_candidate(db, candidate_id, user.id)
    return ApiResponse(data={"ok": ok})


@sub_router.post("/governance/entities/merge")
async def api_merge_entities(
    payload: MergeEntitiesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    ok = await merge_entities(db, payload.source_entity_ids, payload.target_entity_id, user.id, payload.reason)
    return ApiResponse(data={"ok": ok})


@sub_router.post("/governance/calibrate")
async def api_calibrate(
    payload: CalibrateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    ok = await calibrate_extraction(db, payload.candidate_id, payload.new_name, payload.new_category, user.id)
    return ApiResponse(data={"ok": ok})


@sub_router.get("/governance/pending-count")
async def api_pending_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await get_pending_count(db, user.id)
    return ApiResponse(data={"pending_count": result})


@sub_router.get("/governance/pipeline-debt/dry-run")
async def api_pipeline_debt_dry_run(
    limit: int = Query(default=500, ge=1, le=5000),
    error_marker: str | None = Query(default=None),
    category: list[str] | None = Query(default=None),
    category_limits: str | None = Query(default=None),
    limit_each: int | None = Query(default=None, ge=1, le=5000),
    order: Literal["newest", "oldest"] = Query(default="newest"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await classify_pipeline_lifecycle_debt(
        db,
        limit=limit,
        error_marker=error_marker,
        categories=merge_category_params(None, category),
        category_limits=parse_category_limits_query(category_limits),
        limit_each=limit_each,
        order=order,
    )
    return ApiResponse(data=result)


@sub_router.post("/governance/pipeline-debt/apply")
async def api_pipeline_debt_apply(
    payload: PipelineDebtApplyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await apply_pipeline_lifecycle_debt_action(
        db,
        action=payload.action,
        limit=payload.limit,
        task_ids=payload.task_ids or None,
        dry_run=payload.dry_run,
        categories=merge_category_params(payload.category, payload.categories),
        category_limits=payload.category_limits,
        limit_each=payload.limit_each,
        order=payload.order,
    )
    return ApiResponse(data=result)


@sub_router.get("/governance/pipeline-runs/orphan-running/dry-run")
async def api_orphan_pipeline_run_reconcile_dry_run(
    limit: int = Query(default=500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    _ = user
    result = await dry_run_orphan_pipeline_run_reconcile(db, limit=limit)
    return ApiResponse(data=result)


@sub_router.post("/governance/pipeline-runs/orphan-running/apply")
async def api_orphan_pipeline_run_reconcile_apply(
    payload: PipelineRunReconcileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    _ = user
    result = await apply_orphan_pipeline_run_reconcile(
        db,
        limit=payload.limit,
        run_ids=payload.run_ids or None,
        dry_run=payload.dry_run,
    )
    return ApiResponse(data=result)


@sub_router.post("/governance/pipeline-queue/pending/reconcile")
async def api_pending_pipeline_queue_reconcile(
    payload: PendingPipelineQueueReconcileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    _ = user
    result = await reconcile_pending_pipeline_queue(
        db,
        limit=payload.limit,
        task_ids=payload.task_ids or None,
        dry_run=payload.dry_run,
        categories=merge_category_params(payload.category, payload.categories),
        category_limits=payload.category_limits,
        limit_each=payload.limit_each,
        order=payload.order,
    )
    return ApiResponse(data=result)


@sub_router.get("/governance/lifecycle-debt/dry-run")
async def api_lifecycle_debt_dry_run(
    limit: int = Query(default=500, ge=1, le=5000),
    all_owners: bool = Query(default=False),
    reason: Literal[
        "source_file_deleted",
        "source_file_missing",
        "source_storage_path_missing",
        "source_path_unsafe",
        "source_file_physical_missing",
        "source_unavailable",
    ] = Query(default="source_unavailable"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await audit_lifecycle_debt(
        db,
        None if all_owners else user.id,
        limit=limit,
        reason=reason,
    )
    return ApiResponse(data=result)


@sub_router.post("/governance/lifecycle-debt/archive")
async def api_archive_lifecycle_debt(
    payload: LifecycleArchiveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await archive_source_unavailable_documents(
        db,
        None if payload.all_owners else user.id,
        dry_run=payload.dry_run,
        limit=payload.limit,
        reason=payload.reason,
        confirm=payload.confirm,
        audit_reason=payload.audit_reason,
    )
    return ApiResponse(data=result)


@sub_router.post("/governance/rerun-plan/dry-run")
async def api_rerun_plan_dry_run(
    payload: RerunPlanRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await plan_pipeline_rerun(
        db,
        document_id=payload.document_id,
        owner_id=user.id,
        reason=payload.reason,
        stage=payload.stage,
    )
    return ApiResponse(data=result)


@sub_router.post("/governance/retrieval-feedback/reflect")
async def api_reflect_retrieval_feedback(
    payload: RetrievalFeedbackReflectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    from app.services.maintenance_service import ensure_accepting_new_work
    await ensure_accepting_new_work(db, "knowledge reflection")
    result = await reflect_retrieval_feedback(
        db,
        owner_id=user.id,
        query_context_id=payload.query_context_id,
        conversation_excerpt=payload.conversation_excerpt,
    )
    await db.commit()
    return ApiResponse(data=result)

