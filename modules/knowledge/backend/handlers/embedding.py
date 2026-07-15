"""Embedding-related endpoints (chunk-embedding, cognitive-index, derived-governance)."""
import logging

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.maintenance_service import ensure_accepting_new_work
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.chunk_embedding_service import (
    DEFAULT_CHUNK_EMBEDDING_PROFILE,
    backfill_chunk_embeddings,
    enqueue_chunk_embedding_backfill_task,
    get_chunk_embedding_counts,
)
from ..services.cognitive_index_service import (
    backfill_cognitive_index,
    derive_document_cognitive_index,
)
from ..services.derived_governance_service import (
    backfill_derived_governance,
    derived_governance_counts,
)
from ..services.source_file_state import get_live_document_or_raise

logger = logging.getLogger("v2.knowledge").getChild("handlers.embedding")

sub_router = APIRouter()


class CognitiveBackfillRequest(BaseModel):
    dry_run: bool = True
    limit: int = Field(default=1000, ge=1, le=10000)
    source_root: str = ""
    build_terms: bool = True


class CognitiveDeriveDocumentRequest(BaseModel):
    document_id: int
    limit: int = Field(default=200, ge=1, le=1000)


class DerivedGovernanceBackfillRequest(BaseModel):
    dry_run: bool = True
    limit: int = Field(default=5000, ge=1, le=50000)
    include_lineage: bool = True
    include_conclusion_evidence: bool = True
    include_entity_aliases: bool = True
    include_disambiguation: bool = True


class ChunkEmbeddingBackfillRequest(BaseModel):
    dry_run: bool = True
    limit: int = Field(default=1000, ge=1, le=50000)
    batch_size: int = Field(default=8, ge=1, le=64)
    embedding_profile: str = DEFAULT_CHUNK_EMBEDDING_PROFILE


class ChunkEmbeddingBackfillEnqueueRequest(BaseModel):
    total_limit: int = Field(default=600000, ge=1, le=2_000_000)
    chunk_limit: int = Field(default=96, ge=1, le=5000)
    batch_size: int = Field(default=4, ge=1, le=64)
    priority: int = Field(default=4, ge=0, le=100)
    embedding_profile: str = DEFAULT_CHUNK_EMBEDDING_PROFILE


@sub_router.post("/governance/cognitive-index/backfill")
async def api_cognitive_index_backfill(
    payload: CognitiveBackfillRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    if not payload.dry_run:
        await ensure_accepting_new_work(db, "knowledge backfill")
    result = await backfill_cognitive_index(
        db,
        owner_id=user.id,
        dry_run=payload.dry_run,
        limit=payload.limit,
        source_root=payload.source_root,
        build_terms=payload.build_terms,
    )
    return ApiResponse(data=result)


@sub_router.post("/governance/cognitive-index/derive-document")
async def api_cognitive_index_derive_document(
    payload: CognitiveDeriveDocumentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    await ensure_accepting_new_work(db, "knowledge backfill")
    await get_live_document_or_raise(db, payload.document_id, user.id)
    result = await derive_document_cognitive_index(
        db,
        owner_id=user.id,
        document_id=payload.document_id,
        limit=payload.limit,
    )
    await db.commit()
    return ApiResponse(data=result)


@sub_router.post("/governance/derived/backfill")
async def api_derived_governance_backfill(
    payload: DerivedGovernanceBackfillRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    if not payload.dry_run:
        await ensure_accepting_new_work(db, "knowledge backfill")
    result = await backfill_derived_governance(
        db,
        owner_id=user.id,
        dry_run=payload.dry_run,
        limit=payload.limit,
        include_lineage=payload.include_lineage,
        include_conclusion_evidence=payload.include_conclusion_evidence,
        include_entity_aliases=payload.include_entity_aliases,
        include_disambiguation=payload.include_disambiguation,
    )
    return ApiResponse(data=result)


@sub_router.get("/governance/derived/counts")
async def api_derived_governance_counts(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await derived_governance_counts(db, owner_id=user.id)
    return ApiResponse(data=result)


@sub_router.get("/governance/chunk-embeddings/counts")
async def api_chunk_embedding_counts(
    embedding_profile: str = Query(default=DEFAULT_CHUNK_EMBEDDING_PROFILE),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await get_chunk_embedding_counts(db, owner_id=user.id, profile_key=embedding_profile)
    return ApiResponse(data=result)


@sub_router.post("/governance/chunk-embeddings/backfill")
async def api_chunk_embedding_backfill(
    payload: ChunkEmbeddingBackfillRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    if not payload.dry_run:
        await ensure_accepting_new_work(db, "knowledge backfill")
    result = await backfill_chunk_embeddings(
        db,
        owner_id=user.id,
        profile_key=payload.embedding_profile,
        dry_run=payload.dry_run,
        limit=payload.limit,
        batch_size=payload.batch_size,
    )
    return ApiResponse(data=result)


@sub_router.post("/governance/chunk-embeddings/enqueue")
async def api_chunk_embedding_backfill_enqueue(
    payload: ChunkEmbeddingBackfillEnqueueRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    await ensure_accepting_new_work(db, "knowledge chunk embedding backfill")
    result = await enqueue_chunk_embedding_backfill_task(
        db,
        owner_id=user.id,
        profile_key=payload.embedding_profile,
        total_limit=payload.total_limit,
        chunk_limit=payload.chunk_limit,
        batch_size=payload.batch_size,
        priority=payload.priority,
    )
    await db.commit()
    return ApiResponse(data=result)

