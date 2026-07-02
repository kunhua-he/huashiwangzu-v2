import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_permission
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
    user: User = Depends(require_permission("editor")),
):
    result = await recycle_service.restore_item(db, body.item_type, body.id, user.id)
    if result.get("item_type") == "file" and result.get("origin_id"):
        await _emit_file_event("file.restored", int(result["origin_id"]), user)
    return ApiResponse(data={"message": "Restored", **result})


@router.post("/delete-permanently")
async def delete_permanently(
    body: RestoreRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    await recycle_service.delete_permanently(db, body.item_type, body.id, user.id)
    return ApiResponse(data={"message": "Deleted"})


@router.post("/empty")
async def empty_trash(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    await recycle_service.empty_trash(db, user.id)
    return ApiResponse(data={"message": "Trash emptied"})
