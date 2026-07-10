from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_permission
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services import maintenance_service

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


class SafeRestartRequest(BaseModel):
    reason: str = ""


@router.get("/status")
async def maintenance_status(db: AsyncSession = Depends(get_db)):
    return ApiResponse(data=await maintenance_service.maintenance_snapshot(db))


@router.post("/safe-restart")
async def request_safe_restart(
    body: SafeRestartRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("admin")),
):
    return ApiResponse(data=await maintenance_service.request_safe_restart(
        db,
        requested_by=user.id,
        reason=body.reason,
    ))


@router.post("/cancel")
async def cancel_safe_restart(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission("admin")),
):
    return ApiResponse(data=await maintenance_service.cancel_safe_restart(db))
