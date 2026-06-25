"""Asset service — tracks file lifecycle as Agent assets.

Semantic types:
- draft:       Working set, not yet ready for publication
- published:   Finalized and visible on the desktop
- evidence:    Knowledge retrieval evidence (provenance-tracked)
- generated:   Agent-generated output (docx, xlsx, image, etc.)
- handoff:     File passed to another module/user/workflow
"""
import json
import logging
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.asset import FileAsset
from app.models.file import File
from app.services import file_service
from app.core.exceptions import NotFound, AppException

logger = logging.getLogger("v2.assets")

VALID_ASSET_TYPES = {"draft", "published", "evidence", "generated", "handoff"}
VALID_PUBLISH_STATES = {"draft", "published"}


async def create_asset(
    db: AsyncSession,
    file_id: int,
    owner_id: int,
    asset_type: str = "draft",
    publish_state: str = "draft",
    conversation_id: int | None = None,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
    source_file_id: int | None = None,
    provenance: dict | None = None,
) -> FileAsset:
    """Create an asset record linking a file to its semantic lifecycle."""
    if asset_type not in VALID_ASSET_TYPES:
        raise AppException(f"Invalid asset_type: {asset_type}. Must be one of {VALID_ASSET_TYPES}", status_code=400)
    if publish_state not in VALID_PUBLISH_STATES:
        raise AppException(f"Invalid publish_state: {publish_state}", status_code=400)

    file = await db.get(File, file_id)
    if not file or file.deleted:
        raise NotFound("File not found")

    asset = FileAsset(
        file_id=file_id,
        owner_id=owner_id,
        asset_type=asset_type,
        publish_state=publish_state,
        conversation_id=conversation_id,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        source_file_id=source_file_id,
        provenance=json.dumps(provenance, ensure_ascii=False) if provenance else None,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    logger.info(
        "Asset created: id=%d file_id=%d type=%s owner=%d conv=%s tool=%s",
        asset.id, file_id, asset_type, owner_id, conversation_id, tool_name,
    )
    return asset


async def update_asset_state(
    db: AsyncSession,
    asset_id: int,
    owner_id: int,
    asset_type: str | None = None,
    publish_state: str | None = None,
) -> FileAsset:
    """Update an asset's semantic type or publish state."""
    asset = await db.get(FileAsset, asset_id)
    if not asset:
        raise NotFound("Asset not found")
    if asset.owner_id != owner_id:
        raise AppException("Permission denied", status_code=403)

    if asset_type is not None:
        if asset_type not in VALID_ASSET_TYPES:
            raise AppException(f"Invalid asset_type: {asset_type}", status_code=400)
        asset.asset_type = asset_type
    if publish_state is not None:
        if publish_state not in VALID_PUBLISH_STATES:
            raise AppException(f"Invalid publish_state: {publish_state}", status_code=400)
        asset.publish_state = publish_state

    await db.commit()
    await db.refresh(asset)
    return asset


async def get_asset(db: AsyncSession, asset_id: int) -> FileAsset | None:
    """Get a single asset record."""
    return await db.get(FileAsset, asset_id)


async def get_assets_by_conversation(
    db: AsyncSession,
    conversation_id: int,
    owner_id: int | None = None,
) -> list[dict]:
    """Get all assets for a conversation, with file details."""
    query = (
        select(FileAsset, File)
        .join(File, FileAsset.file_id == File.id)
        .where(FileAsset.conversation_id == conversation_id)
    )
    if owner_id is not None:
        query = query.where(FileAsset.owner_id == owner_id)
    query = query.order_by(FileAsset.created_at.desc())

    result = await db.execute(query)
    rows = result.all()
    return [_asset_to_dict(fa, f) for fa, f in rows]


async def list_user_assets(
    db: AsyncSession,
    owner_id: int,
    asset_type: str | None = None,
    publish_state: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """List assets for a user with optional type/state filters."""
    query = (
        select(FileAsset, File)
        .join(File, FileAsset.file_id == File.id)
        .where(FileAsset.owner_id == owner_id, File.deleted == False)
    )
    if asset_type:
        query = query.where(FileAsset.asset_type == asset_type)
    if publish_state:
        query = query.where(FileAsset.publish_state == publish_state)

    count_q = select(FileAsset).where(FileAsset.owner_id == owner_id)
    if asset_type:
        count_q = count_q.where(FileAsset.asset_type == asset_type)
    if publish_state:
        count_q = count_q.where(FileAsset.publish_state == publish_state)
    total = len((await db.execute(count_q)).scalars().all())

    query = query.order_by(FileAsset.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rows = result.all()
    items = [_asset_to_dict(fa, f) for fa, f in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def publish_asset(
    db: AsyncSession,
    asset_id: int,
    owner_id: int,
) -> FileAsset:
    """Publish a draft asset — transitions publish_state to 'published'."""
    return await update_asset_state(db, asset_id, owner_id, publish_state="published")


async def delete_asset(db: AsyncSession, asset_id: int, owner_id: int) -> None:
    """Soft-delete: just remove the asset label, not the file."""
    asset = await db.get(FileAsset, asset_id)
    if not asset:
        raise NotFound("Asset not found")
    if asset.owner_id != owner_id:
        raise AppException("Permission denied", status_code=403)
    await db.delete(asset)
    await db.commit()


def _asset_to_dict(asset: FileAsset, file: File) -> dict:
    return {
        "id": asset.id,
        "file_id": asset.file_id,
        "owner_id": asset.owner_id,
        "asset_type": asset.asset_type,
        "publish_state": asset.publish_state,
        "conversation_id": asset.conversation_id,
        "tool_name": asset.tool_name,
        "tool_call_id": asset.tool_call_id,
        "source_file_id": asset.source_file_id,
        "provenance": json.loads(asset.provenance) if asset.provenance else None,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
        "file_name": f"{file.name}.{file.extension}" if file.extension else file.name,
        "file_size": file.size,
        "file_mime": file.mime_type,
    }
