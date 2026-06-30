"""Artifact lifecycle REST endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services import artifact_service as svc

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


class CreateArtifactRequest(BaseModel):
    name: str
    extension: str = ""
    mime_type: str | None = None
    kind: str | None = None
    storage_mode: str = "file"
    content_text: str | None = None
    folder_id: int | None = None
    conflict_policy: str = "create_version"


class UpdateMetadataRequest(BaseModel):
    name: str | None = None
    folder_id: int | None = None
    conflict_policy: str = "create_version"


class ReplaceContentRequest(BaseModel):
    content_text: str | None = None
    content_json: dict | None = None
    operation_summary: str = ""
    create_version: bool = True


class ExportRequest(BaseModel):
    target_format: str | None = None


class PublishRequest(BaseModel):
    target_file_id: int | None = None
    conflict_policy: str = "create_version"


class ReplaceFromArtifactRequest(BaseModel):
    target_file_id: int
    source_artifact_id: int
    conflict_policy: str = "create_version"


class VersionCreateRequest(BaseModel):
    operation_summary: str = ""


@router.get("/health")
async def health():
    return ApiResponse(data={"module": "artifacts", "status": "ok"})


@router.post("")
async def api_create_artifact(
    body: CreateArtifactRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.create_artifact(
        db, user.id,
        name=body.name,
        extension=body.extension,
        mime_type=body.mime_type,
        kind=body.kind,
        storage_mode=body.storage_mode,
        content_text=body.content_text,
        folder_id=body.folder_id,
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.get("")
async def api_list_artifacts(
    folder_id: int | None = Query(None),
    kind: str | None = Query(None),
    extension: str | None = Query(None),
    status: str = Query("active"),
    page: int = Query(1),
    page_size: int = Query(50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await svc.list_artifacts(
        db, user.id, folder_id=folder_id, kind=kind,
        extension=extension, status=status,
        page=page, page_size=page_size,
    )
    return ApiResponse(data=result)


@router.get("/{artifact_id}")
async def api_get_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await svc.get_artifact(db, artifact_id, user.id)
    return ApiResponse(data=result)


@router.put("/{artifact_id}")
async def api_update_metadata(
    artifact_id: int,
    body: UpdateMetadataRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.update_artifact_metadata(
        db, artifact_id, user.id,
        name=body.name,
        folder_id=body.folder_id,
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.put("/{artifact_id}/content")
async def api_replace_content(
    artifact_id: int,
    body: ReplaceContentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.replace_artifact_content(
        db, artifact_id, user.id,
        content_text=body.content_text,
        content_json=body.content_json,
        operation_type="update",
        operation_summary=body.operation_summary,
        create_version=body.create_version,
    )
    return ApiResponse(data=result)


@router.delete("/{artifact_id}")
async def api_delete_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.delete_artifact(db, artifact_id, user.id, soft=True)
    return ApiResponse(data=result)


@router.post("/{artifact_id}/restore")
async def api_restore_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.restore_artifact(db, artifact_id, user.id)
    return ApiResponse(data=result)


@router.post("/{artifact_id}/rename")
async def api_rename_artifact(
    artifact_id: int,
    body: UpdateMetadataRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.rename_artifact(
        db, artifact_id, user.id,
        new_name=body.name or "",
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.post("/{artifact_id}/copy")
async def api_copy_artifact(
    artifact_id: int,
    body: UpdateMetadataRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.copy_artifact(
        db, artifact_id, user.id,
        target_folder_id=body.folder_id,
        new_name=body.name,
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.post("/{artifact_id}/move")
async def api_move_artifact(
    artifact_id: int,
    body: UpdateMetadataRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.move_artifact(
        db, artifact_id, user.id,
        target_folder_id=body.folder_id,
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.post("/{artifact_id}/versions")
async def api_create_version(
    artifact_id: int,
    body: VersionCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.create_artifact_version(
        db, artifact_id, user.id,
        operation_summary=body.operation_summary,
    )
    return ApiResponse(data=result)


@router.get("/{artifact_id}/versions")
async def api_list_versions(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await svc.list_artifact_versions(db, artifact_id, user.id)
    return ApiResponse(data=result)


@router.post("/{artifact_id}/versions/{version_id}/restore")
async def api_restore_version(
    artifact_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.restore_artifact_version(db, artifact_id, version_id, user.id)
    return ApiResponse(data=result)


@router.post("/{artifact_id}/export")
async def api_export_artifact(
    artifact_id: int,
    body: ExportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await svc.export_artifact(
        db, artifact_id, user.id,
        target_format=body.target_format,
    )
    return ApiResponse(data=result)


@router.post("/{artifact_id}/publish")
async def api_publish_artifact(
    artifact_id: int,
    body: PublishRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.publish_artifact(
        db, artifact_id, user.id,
        target_file_id=body.target_file_id,
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.post("/replace-from-artifact")
async def api_replace_from_artifact(
    body: ReplaceFromArtifactRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    result = await svc.replace_file_from_artifact(
        db, user.id,
        target_file_id=body.target_file_id,
        source_artifact_id=body.source_artifact_id,
        conflict_policy=body.conflict_policy,
    )
    return ApiResponse(data=result)


@router.get("/{artifact_id}/operations")
async def api_list_operations(
    artifact_id: int,
    page: int = Query(1),
    page_size: int = Query(50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await svc.list_operations(
        db, artifact_id, user.id,
        page=page, page_size=page_size,
    )
    return ApiResponse(data=result)
