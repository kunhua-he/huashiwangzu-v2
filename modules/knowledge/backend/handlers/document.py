"""Document CRUD endpoints."""
import logging

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.maintenance_service import ensure_accepting_new_work
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..services.document_service import (
    enqueue_pipeline_task,
    get_document,
    list_documents,
    list_documents_by_file_ids,
    parse_and_index_document,
    register_document,
    soft_delete_document,
)
from ..services.ingest_status_service import get_ingest_status
from ..services.source_file_state import get_live_document_or_raise

logger = logging.getLogger("v2.knowledge").getChild("handlers.document")

sub_router = APIRouter()


class RegisterDocumentRequest(BaseModel):
    file_id: int
    catalog_id: int | None = None


class DocumentsByFilesRequest(BaseModel):
    file_ids: list[int] = Field(default_factory=list, max_length=200)


class ParseDocumentRequest(BaseModel):
    document_id: int
    extract_graph: bool = True


@sub_router.post("/documents")
async def api_register_document(
    payload: RegisterDocumentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await register_document(db, payload.file_id, user.id, payload.catalog_id)
    return ApiResponse(data=result)


@sub_router.get("/documents")
async def api_list_documents(
    catalog_id: int | None = Query(default=None),
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await list_documents(db, user.id, catalog_id, keyword, page, page_size)
    return ApiResponse(data=result)


@sub_router.get("/documents/{document_id}")
async def api_get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await get_document(db, document_id, user.id)
    return ApiResponse(data=result)


@sub_router.post("/documents/by-files")
async def api_documents_by_files(
    payload: DocumentsByFilesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await list_documents_by_file_ids(db, user.id, payload.file_ids[:200])
    return ApiResponse(data={"items": result})


@sub_router.delete("/documents/{document_id}")
async def api_delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    await soft_delete_document(db, document_id, user.id)
    return ApiResponse(data={"deleted": True})


@sub_router.post("/documents/parse")
async def api_parse_document(
    payload: ParseDocumentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    await ensure_accepting_new_work(db, "knowledge parsing")
    result = await parse_and_index_document(
        db,
        payload.document_id,
        user.id,
        caller=f"user:{user.id}",
        extract_graph=payload.extract_graph,
    )
    return ApiResponse(data=result)


@sub_router.get("/documents/{document_id}/ingest-status")
async def api_document_ingest_status(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    """Unified ingest queue + document stage status for Agent/frontend polling."""
    result = await get_ingest_status(db, document_id, user.id)
    return ApiResponse(data=result)

