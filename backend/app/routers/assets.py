"""Asset API endpoints — manage file lifecycle as Agent assets.

All asset operations validate file access via ``file_service.check_file_access``
before returning or modifying records.  The asset layer is a semantic overlay;
the bottom permission boundary remains ``check_file_access``.
"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.common import ApiResponse
from app.middleware.auth import require_permission
from app.models.user import User
from app.services import asset_service
from app.services import file_service
from app.core.exceptions import NotFound

logger = logging.getLogger("v2.assets.api")

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("/create")
async def create_asset(
    file_id: int,
    asset_type: str = "draft",
    publish_state: str = "draft",
    conversation_id: int | None = None,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
    source_file_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    """Create an asset record for an existing file.
    
    File must be accessible to the user (owner or shared).
    """
    await file_service.check_file_access(db, file_id, user.id)
    asset = await asset_service.create_asset(
        db, file_id, user.id, asset_type, publish_state,
        conversation_id, tool_name, tool_call_id, source_file_id,
    )
    return ApiResponse(data={
        "id": asset.id,
        "file_id": asset.file_id,
        "asset_type": asset.asset_type,
        "publish_state": asset.publish_state,
    })


@router.patch("/{asset_id}/publish")
async def publish_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    """Publish an asset — transitions publish_state to 'published'."""
    asset = await asset_service.publish_asset(db, asset_id, user.id)
    return ApiResponse(data={
        "id": asset.id,
        "file_id": asset.file_id,
        "asset_type": asset.asset_type,
        "publish_state": asset.publish_state,
    })


@router.patch("/{asset_id}/state")
async def update_asset_state(
    asset_id: int,
    asset_type: str | None = None,
    publish_state: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    """Update asset type or publish state."""
    asset = await asset_service.update_asset_state(
        db, asset_id, user.id, asset_type, publish_state,
    )
    return ApiResponse(data={
        "id": asset.id,
        "file_id": asset.file_id,
        "asset_type": asset.asset_type,
        "publish_state": asset.publish_state,
    })


@router.get("/by-conversation/{conversation_id}")
async def get_assets_by_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    """List all assets belonging to a conversation."""
    items = await asset_service.get_assets_by_conversation(
        db, conversation_id, owner_id=user.id,
    )
    return ApiResponse(data={"items": items, "total": len(items)})


@router.get("")
async def list_assets(
    asset_type: str | None = Query(None),
    publish_state: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("viewer")),
):
    """List the current user's assets with optional filters."""
    result = await asset_service.list_user_assets(
        db, user.id, asset_type, publish_state, page, page_size,
    )
    return ApiResponse(data=result)


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("editor")),
):
    """Delete an asset label (does not delete the underlying file)."""
    await asset_service.delete_asset(db, asset_id, user.id)
    return ApiResponse(data={"deleted": True})
