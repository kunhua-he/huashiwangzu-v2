import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.file import File, Folder
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.recycle import RecycleItemResponse, RestoreRequest
from app.services import recycle_service

router = APIRouter(prefix="/api/recycle", tags=["recycle"])
logger = logging.getLogger("v2.recycle.router")


async def _emit_file_event(event_name: str, file_id: int, user: User) -> None:
    try:
        from app.services.module_events import emit_module_event

        await emit_module_event(
            event_name,
            {"file_id": file_id, "owner_id": user.id},
            caller=f"user:{user.id}",
            caller_role=user.role,
        )
    except Exception as exc:
        logger.warning("%s event emission failed for file_id=%d: %s", event_name, file_id, exc)


async def _collect_folder_file_ids(db: AsyncSession, folder_id: int, owner_id: int) -> list[int]:
    file_rows = await db.execute(
        select(File.id).where(
            File.folder_id == folder_id,
            File.owner_id == owner_id,
            File.deleted.is_(True),
        )
    )
    file_ids = [int(file_id) for file_id in file_rows.scalars().all()]
    folder_rows = await db.execute(
        select(Folder.id).where(
            Folder.parent_id == folder_id,
            Folder.owner_id == owner_id,
            Folder.deleted.is_(True),
        )
    )
    for child_folder_id in folder_rows.scalars().all():
        file_ids.extend(await _collect_folder_file_ids(db, int(child_folder_id), owner_id))
    return file_ids


@router.get("/list")
async def list_recycle(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    enriched = await recycle_service.get_recycle_list(db, user.id)
    data = []
    for item, fmt in enriched:
        rec = RecycleItemResponse.model_validate(item)
        rec.format = fmt
        data.append(rec)
    return ApiResponse(data=data)


@router.post("/restore")
async def restore(
    body: RestoreRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    folder_file_ids: list[int] = []
    if body.item_type == "folder":
        from app.models.recycle import RecycleItem

        recycle_item = await db.get(RecycleItem, body.id)
        if recycle_item and recycle_item.owner_id == user.id and recycle_item.item_type == "folder":
            folder_file_ids = await _collect_folder_file_ids(db, int(recycle_item.origin_id), user.id)
    result = await recycle_service.restore_item(db, body.item_type, body.id, user.id)
    if result.get("item_type") == "file" and result.get("origin_id"):
        await _emit_file_event("file.restored", int(result["origin_id"]), user)
    elif result.get("item_type") == "folder":
        for file_id in folder_file_ids:
            await _emit_file_event("file.restored", file_id, user)
    return ApiResponse(data={"message": "Restored", **result})


@router.post("/delete-permanently")
async def delete_permanently(
    body: RestoreRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    result = await recycle_service.delete_permanently(db, body.item_type, body.id, user.id)
    for file_id in result.get("permanently_deleted_file_ids", []):
        await _emit_file_event("file.permanent_deleted", file_id, user)
    return ApiResponse(data={"message": "Deleted", **result})


@router.post("/empty")
async def empty_trash(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    result = await recycle_service.empty_trash(db, user.id)
    for file_id in result.get("permanently_deleted_file_ids", []):
        await _emit_file_event("file.permanent_deleted", file_id, user)
    return ApiResponse(data={"message": "Trash emptied", **result})
