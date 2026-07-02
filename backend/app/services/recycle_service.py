import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, NotFound
from app.models.file import File, Folder
from app.models.file_share import FileShare
from app.models.recycle import RecycleItem

logger = logging.getLogger("v2.recycle")


async def get_recycle_list(db: AsyncSession, owner_id: int):
    result = await db.execute(
        select(RecycleItem).where(RecycleItem.owner_id == owner_id).order_by(RecycleItem.deleted_at.desc())
    )
    items = result.scalars().all()

    file_ids = [item.origin_id for item in items if item.item_type == "file"]
    file_ext_map: dict[int, str | None] = {}
    if file_ids:
        files = await db.execute(
            select(File).where(File.id.in_(file_ids))
        )
        for f in files.scalars():
            file_ext_map[f.id] = f.extension

    enriched = []
    for item in items:
        fmt = None
        if item.item_type == "file":
            fmt = file_ext_map.get(item.origin_id)
        enriched.append((item, fmt))

    return enriched


async def restore_item(db: AsyncSession, item_type: str, item_id: int, owner_id: int):
    recycle = await db.get(RecycleItem, item_id)
    if not recycle or recycle.owner_id != owner_id or recycle.item_type != item_type:
        raise NotFound("Recycle item not found")

    moved_to_root = False
    original_parent = ""

    if recycle.item_type == "file":
        file = await db.get(File, recycle.origin_id)
        if not file or file.owner_id != owner_id:
            raise NotFound("Original file no longer accessible")
        # Check name conflict at restore destination
        await _check_file_name_conflict(db, file.name, file.extension, file.folder_id, owner_id)
        # Check if original parent folder still exists
        if file.folder_id:
            parent = await db.get(Folder, file.folder_id)
            if not parent or parent.deleted:
                # Fallback to root
                moved_to_root = True
                original_parent = parent.name if parent else ""
                file.folder_id = None
        file.deleted = False
        file.deleted_at = None
    elif recycle.item_type == "folder":
        folder = await db.get(Folder, recycle.origin_id)
        if not folder or folder.owner_id != owner_id:
            raise NotFound("Original folder no longer accessible")
        # Check name conflict at restore destination
        await _check_folder_name_conflict(db, folder.name, folder.parent_id, owner_id)
        # Ancestor path recovery: restore deleted parent folders up the chain
        await _restore_ancestor_path(db, folder, owner_id)
        # Check if original parent folder exists
        if folder.parent_id:
            parent = await db.get(Folder, folder.parent_id)
            if not parent or parent.deleted:
                moved_to_root = True
                original_parent = parent.name if parent else ""
                folder.parent_id = None
        await _recursive_restore_folder(db, folder.id)

    await db.delete(recycle)
    await db.commit()

    result = {
        "success": True,
        "item_type": recycle.item_type,
        "origin_id": recycle.origin_id,
    }
    if moved_to_root:
        result["moved_to_root"] = True
        result["original_parent"] = original_parent
    return result


async def _restore_ancestor_path(db: AsyncSession, folder: Folder, owner_id: int):
    """Recursively restore deleted ancestor folders in the path."""
    if not folder.parent_id:
        return
    parent = await db.get(Folder, folder.parent_id)
    if parent and parent.deleted and parent.owner_id == owner_id:
        parent.deleted = False
        parent.deleted_at = None
        # Continue up the chain
        await _restore_ancestor_path(db, parent, owner_id)
    # Also remove any RecycleItem records for restored ancestors
    if parent:
        ancestor_recycle = await db.execute(
            select(RecycleItem).where(
                RecycleItem.origin_id == parent.id,
                RecycleItem.item_type == "folder",
                RecycleItem.owner_id == owner_id,
            )
        )
        for item in ancestor_recycle.scalars():
            await db.delete(item)


async def _check_file_name_conflict(db: AsyncSession, name: str, extension: str, folder_id: int | None, owner_id: int):
    """Check if a file with the same name already exists at the target location."""
    existing = await db.execute(
        select(File).where(
            File.name == name,
            File.extension == extension,
            File.folder_id == folder_id,
            File.owner_id == owner_id,
            File.deleted.is_(False),
        )
    )
    if existing.scalar_one_or_none():
        raise AppException("A file with the same name already exists in the target directory", status_code=409)


async def _check_folder_name_conflict(db: AsyncSession, name: str, parent_id: int | None, owner_id: int):
    """Check if a folder with the same name already exists at the target location."""
    existing = await db.execute(
        select(Folder).where(
            Folder.name == name,
            Folder.parent_id == parent_id,
            Folder.owner_id == owner_id,
            Folder.deleted.is_(False),
        )
    )
    if existing.scalar_one_or_none():
        raise AppException("A folder with the same name already exists in the target directory", status_code=409)


async def _recursive_restore_folder(db: AsyncSession, folder_id: int):
    folder = await db.get(Folder, folder_id)
    if folder and folder.deleted:
        folder.deleted = False
        folder.deleted_at = None

    files = await db.execute(
        select(File).where(File.folder_id == folder_id, File.deleted.is_(True))
    )
    for f in files.scalars():
        f.deleted = False
        f.deleted_at = None

    subfolders = await db.execute(
        select(Folder).where(Folder.parent_id == folder_id, Folder.deleted.is_(True))
    )
    for sf in subfolders.scalars():
        await _recursive_restore_folder(db, sf.id)


async def delete_permanently(db: AsyncSession, item_type: str, item_id: int, owner_id: int):
    recycle = await db.get(RecycleItem, item_id)
    if not recycle or recycle.owner_id != owner_id or recycle.item_type != item_type:
        raise NotFound("Recycle item not found")

    if recycle.item_type == "file":
        file = await db.get(File, recycle.origin_id)
        if file:
            # Clean up share records for this file
            shares = await db.execute(
                select(FileShare).where(FileShare.file_id == file.id)
            )
            for share in shares.scalars():
                await db.delete(share)
            # Handle ref_count and disk cleanup
            other_refs = await db.execute(
                select(File).where(
                    File.md5_hash == file.md5_hash,
                    File.deleted.is_(False),
                    File.id != file.id,
                ).with_for_update()
            )
            other_ref_list = other_refs.scalars().all()
            if not other_ref_list:
                # Last reference — delete disk file
                path = _resolve_storage_path(file)
                if path and path.exists():
                    try:
                        path.unlink()
                    except Exception as exc:
                        logger.warning("Failed to unlink storage file %s: %s", path, exc)
            await db.delete(file)
    elif recycle.item_type == "folder":
        folder = await db.get(Folder, recycle.origin_id)
        if folder:
            await _recursive_permanent_delete_folder(db, folder.id, owner_id)
            if folder.deleted:
                await db.delete(folder)

    await db.delete(recycle)
    await db.commit()


async def _recursive_permanent_delete_folder(db: AsyncSession, folder_id: int, owner_id: int = 0):
    files = await db.execute(
        select(File).where(File.folder_id == folder_id, File.deleted.is_(True))
    )
    for f in files.scalars():
        # Clean up shares for each file
        shares = await db.execute(
            select(FileShare).where(FileShare.file_id == f.id)
        )
        for share in shares.scalars():
            await db.delete(share)
        # Check ref_count before deleting disk
        other_refs = await db.execute(
            select(File).where(
                File.md5_hash == f.md5_hash,
                File.deleted.is_(False),
                File.id != f.id,
            ).with_for_update()
        )
        if not other_refs.scalars().all():
            path = _resolve_storage_path(f)
            if path and path.exists():
                try:
                    path.unlink()
                except Exception as exc:
                    logger.warning("Failed to unlink storage file %s: %s", path, exc)
        await db.delete(f)

    subfolders = await db.execute(
        select(Folder).where(Folder.parent_id == folder_id, Folder.deleted.is_(True))
    )
    for sf in subfolders.scalars():
        await _recursive_permanent_delete_folder(db, sf.id, owner_id)
        await db.delete(sf)


async def empty_trash(db: AsyncSession, owner_id: int):
    items = await db.execute(
        select(RecycleItem).where(RecycleItem.owner_id == owner_id)
    )
    for item in items.scalars():
        if item.item_type == "file":
            file = await db.get(File, item.origin_id)
            if file:
                # Clean up shares
                shares = await db.execute(
                    select(FileShare).where(FileShare.file_id == file.id)
                )
                for share in shares.scalars():
                    await db.delete(share)
                # Check ref_count
                other_refs = await db.execute(
                    select(File).where(
                        File.md5_hash == file.md5_hash,
                        File.deleted.is_(False),
                        File.id != file.id,
                    ).with_for_update()
                )
                if not other_refs.scalars().all():
                    path = _resolve_storage_path(file)
                    if path and path.exists():
                        try:
                            path.unlink()
                        except Exception as exc:
                            logger.warning("Failed to unlink storage file %s: %s", path, exc)
                await db.delete(file)
        elif item.item_type == "folder":
            folder = await db.get(Folder, item.origin_id)
            if folder:
                await _recursive_permanent_delete_folder(db, folder.id, owner_id)
                if folder.deleted:
                    await db.delete(folder)
        await db.delete(item)
    await db.commit()


def _resolve_storage_path(file: File):
    from pathlib import Path

    from app.config import get_settings

    settings = get_settings()
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    if not file.storage_path:
        return None
    full_path = (upload_root / file.storage_path).resolve()
    if os.path.commonpath([str(upload_root), str(full_path)]) != str(upload_root):
        return None
    return full_path
