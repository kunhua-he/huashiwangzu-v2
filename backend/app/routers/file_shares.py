from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services import file_share_service as svc
from app.schemas.common import ApiResponse
from app.core.exceptions import ValidationError
from pydantic import BaseModel

router = APIRouter(prefix="/api/files/share", tags=["File Shares"])


class ShareCreateRequest(BaseModel):
    file_id: int
    target_user_id: int
    permission: str = "read"
    scope: dict | None = None
    expiry: str | None = None
    reason: str | None = None
    publish: bool = False
    reshare: bool = False


class ShareUpdateRequest(BaseModel):
    permission: str | None = None
    scope: dict | None = None
    expiry: str | None = None
    reason: str | None = None
    publish: bool | None = None
    reshare: bool | None = None


def _parse_expiry(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _share_to_dict(share) -> dict:
    return {
        "id": share.id,
        "file_id": share.file_id,
        "shared_by_owner_id": share.shared_by_owner_id,
        "shared_with_user_id": share.shared_with_user_id,
        "permission": share.permission,
        "scope": share.scope,
        "expiry": share.expiry.isoformat() if share.expiry else None,
        "reason": share.reason,
        "publish": share.publish,
        "reshare": share.reshare,
        "created_at": share.created_at.isoformat() if share.created_at else None,
    }


@router.post("")
async def create_share(
    body: ShareCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    share = await svc.create_share(
        db,
        file_id=body.file_id,
        shared_by_user_id=current_user.id,
        shared_with_user_id=body.target_user_id,
        permission=body.permission,
        scope=body.scope,
        expiry=_parse_expiry(body.expiry),
        reason=body.reason,
        publish=body.publish,
        reshare=body.reshare,
    )
    return ApiResponse(success=True, data=_share_to_dict(share))


@router.put("/{share_id}")
async def update_share(
    share_id: int,
    body: ShareUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    share = await svc.update_share(
        db,
        share_id=share_id,
        user_id=current_user.id,
        permission=body.permission,
        scope=body.scope,
        expiry=_parse_expiry(body.expiry),
        reason=body.reason,
        publish=body.publish,
        reshare=body.reshare,
    )
    return ApiResponse(success=True, data=_share_to_dict(share))


@router.get("/received")
async def received_shares(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    keyword: str = Query(""),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await svc.get_received_shares(db, current_user.id, page, page_size, keyword)
    return ApiResponse(success=True, data=result)


@router.get("/sent")
async def sent_shares(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await svc.get_sent_shares(db, current_user.id, page, page_size)
    return ApiResponse(success=True, data=result)


@router.delete("/{share_id}")
async def delete_share(
    share_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await svc.delete_share(db, share_id, current_user.id)
    return ApiResponse(success=True, data={"message": "Share cancelled"})


@router.get("/check/{file_id}")
async def check_access(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await svc.check_file_access(db, file_id, current_user.id)
    return ApiResponse(success=True, data=result)


@router.post("/resolve")
async def resolve_permission(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unified resource permission resolution endpoint."""
    resource_type = body.get("resource_type", "file")
    resource_id = body.get("resource_id")
    if not resource_id:
        raise ValidationError("resource_id is required")
    result = await svc.resolve_resource_permission(
        db, resource_type, resource_id, current_user.id
    )
    return ApiResponse(success=True, data=result)
