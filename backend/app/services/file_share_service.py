from datetime import datetime, timezone
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.file import File, Folder
from app.models.file_share import FileShare
from app.models.user import User
from app.core.exceptions import NotFound, AppException

RESOURCE_TYPES = ("file", "document_ir", "artifact", "evidence")


async def check_file_access(db: AsyncSession, file_id: int, user_id: int) -> dict:
    """Check if a user can access a file. Returns access info with collab fields."""
    file = await db.get(File, file_id)
    if not file or file.deleted:
        return {"accessible": False, "permission": None}

    if file.owner_id == user_id:
        return {
            "accessible": True,
            "permission": "owner",
            "scope": None,
            "expiry": None,
            "reason": None,
            "publish": True,
            "reshare": True,
        }

    share = await db.execute(
        select(FileShare).where(
            FileShare.file_id == file_id,
            FileShare.shared_with_user_id == user_id,
            or_(FileShare.expiry.is_(None), FileShare.expiry > datetime.now(timezone.utc)),
        )
    )
    share_record = share.scalar_one_or_none()
    if share_record:
        return {
            "accessible": True,
            "permission": share_record.permission,
            "scope": share_record.scope,
            "expiry": share_record.expiry.isoformat() if share_record.expiry else None,
            "reason": share_record.reason,
            "publish": share_record.publish,
            "reshare": share_record.reshare,
        }

    return {"accessible": False, "permission": None}


async def resolve_resource_permission(
    db: AsyncSession,
    resource_type: str,
    resource_id: int,
    user_id: int,
) -> dict:
    """Unified resource permission resolver.
    
    Returns a consistent permission dict for any resource type:
    {accessible, permission, scope, expiry, reason, publish, reshare}
    
    Supported resource types: file, document_ir, artifact, evidence
    """
    if resource_type == "file":
        return await check_file_access(db, resource_id, user_id)

    if resource_type == "document_ir":
        from app.models.office import FileJsonPackage
        pkg = await db.get(FileJsonPackage, resource_id)
        if not pkg:
            return {"accessible": False, "permission": None}
        return await check_file_access(db, pkg.file_id, user_id)

    if resource_type == "artifact":
        from app.models.asset import FileAsset
        asset = await db.get(FileAsset, resource_id)
        if not asset:
            return {"accessible": False, "permission": None}
        return await check_file_access(db, asset.file_id, user_id)

    if resource_type == "evidence":
        from app.models.asset import FileAsset
        asset = await db.get(FileAsset, resource_id)
        if not asset:
            return {"accessible": False, "permission": None}
        return await check_file_access(db, asset.file_id, user_id)

    return {"accessible": False, "permission": None}


async def require_resource_permission(
    db: AsyncSession,
    resource_type: str,
    resource_id: int,
    user_id: int,
    min_permission: str = "read",
) -> dict:
    """Check and return resource permission, raising if insufficient.
    
    Permission hierarchy: owner > edit > comment > read
    """
    result = await resolve_resource_permission(db, resource_type, resource_id, user_id)
    if not result["accessible"]:
        raise AppException(f"No access to {resource_type}", status_code=403)

    perm = result["permission"]
    if perm == "owner":
        return result

    level = {"owner": 4, "edit": 3, "comment": 2, "read": 1}
    min_lv = level.get(min_permission, 1)
    actual_lv = level.get(perm, 0)
    if actual_lv < min_lv:
        raise AppException(
            f"Requires at least '{min_permission}' permission on {resource_type}, got '{perm}'",
            status_code=403,
        )
    return result


async def create_share(
    db: AsyncSession,
    file_id: int,
    shared_by_user_id: int,
    shared_with_user_id: int,
    permission: str = "read",
    scope: dict | None = None,
    expiry: datetime | None = None,
    reason: str | None = None,
    publish: bool = False,
    reshare: bool = False,
) -> FileShare:
    """Share a file with another user. Reuses existing share if already shared."""
    file = await db.get(File, file_id)
    if not file or file.deleted:
        raise NotFound("File not found")
    if file.owner_id != shared_by_user_id:
        raise AppException("Only the file owner can share", status_code=403)

    target_user = await db.get(User, shared_with_user_id)
    if not target_user:
        raise NotFound("Target user not found")

    if shared_by_user_id == shared_with_user_id:
        raise AppException("Cannot share a file with yourself", status_code=400)

    if permission not in ("read", "edit", "comment"):
        raise AppException("Permission must be 'read', 'edit', or 'comment'", status_code=400)

    if expiry and expiry <= datetime.now(timezone.utc):
        raise AppException("Expiry must be in the future", status_code=400)

    # Check if already shared — update existing
    existing = await db.execute(
        select(FileShare).where(
            FileShare.file_id == file_id,
            FileShare.shared_by_owner_id == shared_by_user_id,
            FileShare.shared_with_user_id == shared_with_user_id,
        )
    )
    share = existing.scalar_one_or_none()
    if share:
        share.permission = permission
        share.scope = scope
        share.expiry = expiry
        share.reason = reason
        share.publish = publish
        share.reshare = reshare
        await db.commit()
        await db.refresh(share)
        return share

    share = FileShare(
        file_id=file_id,
        shared_by_owner_id=shared_by_user_id,
        shared_with_user_id=shared_with_user_id,
        permission=permission,
        scope=scope,
        expiry=expiry,
        reason=reason,
        publish=publish,
        reshare=reshare,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return share


async def update_share(
    db: AsyncSession,
    share_id: int,
    user_id: int,
    permission: str | None = None,
    scope: dict | None = None,
    expiry: datetime | None = None,
    reason: str | None = None,
    publish: bool | None = None,
    reshare: bool | None = None,
) -> FileShare:
    """Update an existing share. Only the original sharer can update."""
    share = await db.get(FileShare, share_id)
    if not share:
        raise NotFound("Share not found")
    if share.shared_by_owner_id != user_id:
        raise AppException("Only the sharer can update the share", status_code=403)

    if permission is not None:
        if permission not in ("read", "edit", "comment"):
            raise AppException("Permission must be 'read', 'edit', or 'comment'", status_code=400)
        share.permission = permission
    if scope is not None:
        share.scope = scope
    if expiry is not None:
        if expiry <= datetime.now(timezone.utc):
            raise AppException("Expiry must be in the future", status_code=400)
        share.expiry = expiry
    if reason is not None:
        share.reason = reason
    if publish is not None:
        share.publish = publish
    if reshare is not None:
        share.reshare = reshare

    await db.commit()
    await db.refresh(share)
    return share


async def delete_share(db: AsyncSession, share_id: int, user_id: int) -> None:
    """Cancel a share. Only the original sharer can cancel."""
    share = await db.get(FileShare, share_id)
    if not share:
        raise NotFound("Share not found")
    if share.shared_by_owner_id != user_id:
        raise AppException("Only the sharer can cancel the share", status_code=403)
    await db.delete(share)
    await db.commit()


async def get_received_shares(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 50,
    keyword: str = "",
) -> dict:
    """Get files shared with a user."""
    query = (
        select(FileShare, File, User.display_name.label("shared_by_name"))
        .join(File, FileShare.file_id == File.id)
        .join(User, FileShare.shared_by_owner_id == User.id)
        .where(
            FileShare.shared_with_user_id == user_id,
            File.deleted == False,
        )
    )
    if keyword:
        query = query.where(File.name.ilike(f"%{keyword}%"))

    query = query.order_by(FileShare.created_at.desc())
    # Count with same filters (deleted=False, keyword)
    count_q = select(FileShare).join(File, FileShare.file_id == File.id).where(
        FileShare.shared_with_user_id == user_id,
        File.deleted == False,
    )
    if keyword:
        count_q = count_q.where(File.name.ilike(f"%{keyword}%"))
    total = len((await db.execute(count_q)).scalars().all())

    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    items = []
    for share, file, shared_by_name in result.all():
        items.append({
            "id": share.id,
            "file_id": file.id,
            "file_name": file.name,
            "extension": file.extension,
            "size": file.size,
            "permission": share.permission,
            "scope": share.scope,
            "expiry": share.expiry.isoformat() if share.expiry else None,
            "reason": share.reason,
            "publish": share.publish,
            "reshare": share.reshare,
            "shared_by_name": shared_by_name,
            "created_at": share.created_at.isoformat() if share.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_sent_shares(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Get files shared by a user."""
    query = (
        select(FileShare, File, User.display_name.label("shared_with_name"))
        .join(File, FileShare.file_id == File.id)
        .join(User, FileShare.shared_with_user_id == User.id)
        .where(FileShare.shared_by_owner_id == user_id)
        .order_by(FileShare.created_at.desc())
    )
    total = len((await db.execute(
        select(FileShare).join(File, FileShare.file_id == File.id).where(
            FileShare.shared_by_owner_id == user_id,
            File.deleted == False,
        )
    )).scalars().all())

    result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )
    items = []
    for share, file, shared_with_name in result.all():
        items.append({
            "id": share.id,
            "file_id": file.id,
            "file_name": file.name,
            "extension": file.extension,
            "size": file.size,
            "permission": share.permission,
            "scope": share.scope,
            "expiry": share.expiry.isoformat() if share.expiry else None,
            "reason": share.reason,
            "publish": share.publish,
            "reshare": share.reshare,
            "shared_with_name": shared_with_name,
            "created_at": share.created_at.isoformat() if share.created_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_accessible_file_ids(db: AsyncSession, user_id: int) -> set[int]:
    """Get all file IDs accessible to a user (owned + shared, not expired)."""
    owned = await db.execute(
        select(File.id).where(File.owner_id == user_id, File.deleted == False)
    )
    owned_ids = set(r for (r,) in owned.all())
    shared = await db.execute(
        select(FileShare.file_id).where(
            FileShare.shared_with_user_id == user_id,
            or_(FileShare.expiry.is_(None), FileShare.expiry > datetime.now(timezone.utc)),
        )
    )
    shared_ids = set(r for (r,) in shared.all())
    return owned_ids | shared_ids
