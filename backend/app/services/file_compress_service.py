"""Zip selected files/folders for Finder compress download."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppException, NotFound
from app.models.file import File, Folder


def _resolve_disk_path(storage_path: str | None) -> Path | None:
    if not storage_path:
        return None
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    full = (upload_dir / storage_path).resolve()
    try:
        if upload_dir not in full.parents and full != upload_dir:
            # also allow file directly under upload_dir
            if not str(full).startswith(str(upload_dir)):
                return None
    except Exception:
        return None
    return full if full.exists() and full.is_file() else None


async def _add_folder_to_zip(
    db: AsyncSession,
    *,
    zf: zipfile.ZipFile,
    folder: Folder,
    owner_id: int,
    prefix: str,
) -> None:
    base = f"{prefix}{folder.name}/"
    # ensure empty folder entry
    zf.writestr(base, b"")
    files = await db.execute(
        select(File).where(
            File.folder_id == folder.id,
            File.owner_id == owner_id,
            File.deleted.is_(False),
        )
    )
    for f in files.scalars().all():
        disk = _resolve_disk_path(f.storage_path)
        arc = f"{base}{f.name}{('.' + f.extension) if f.extension else ''}"
        if disk:
            zf.write(disk, arcname=arc)
        else:
            zf.writestr(arc, b"")
    subs = await db.execute(
        select(Folder).where(
            Folder.parent_id == folder.id,
            Folder.owner_id == owner_id,
            Folder.deleted.is_(False),
        )
    )
    for sub in subs.scalars().all():
        await _add_folder_to_zip(db, zf=zf, folder=sub, owner_id=owner_id, prefix=base)


async def build_zip_bytes(
    db: AsyncSession,
    *,
    owner_id: int,
    items: list[dict],
) -> tuple[bytes, str]:
    if not items:
        raise AppException("No items to compress", status_code=400)

    buf = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for raw in items:
            item_type = str(raw.get("item_type") or raw.get("type") or "file")
            item_id = int(raw.get("id"))
            if item_type == "folder":
                folder = await db.get(Folder, item_id)
                if not folder or folder.deleted or folder.owner_id != owner_id:
                    continue
                await _add_folder_to_zip(db, zf=zf, folder=folder, owner_id=owner_id, prefix="")
                added += 1
            else:
                file = await db.get(File, item_id)
                if not file or file.deleted or file.owner_id != owner_id:
                    continue
                disk = _resolve_disk_path(file.storage_path)
                arc = f"{file.name}{('.' + file.extension) if file.extension else ''}"
                if disk:
                    zf.write(disk, arcname=arc)
                else:
                    zf.writestr(arc, b"")
                added += 1

    if added == 0:
        raise NotFound("No accessible items to compress")

    name = "归档.zip"
    if len(items) == 1:
        only = items[0]
        only_id = int(only.get("id"))
        only_type = str(only.get("item_type") or only.get("type") or "file")
        if only_type == "folder":
            folder = await db.get(Folder, only_id)
            if folder:
                name = f"{folder.name}.zip"
        else:
            file = await db.get(File, only_id)
            if file:
                name = f"{file.name}.zip"

    return buf.getvalue(), name


async def extract_zip_file(
    db: AsyncSession,
    *,
    owner_id: int,
    file_id: int,
    target_folder_id: int | None = None,
) -> dict:
    """Extract a zip file owned by user into target folder (default: zip's parent)."""
    import zipfile as zfmod

    from app.services.file_service import next_available_folder_name

    src = await db.get(File, file_id)
    if not src or src.deleted or src.owner_id != owner_id:
        raise NotFound("Zip file not found")
    ext = (src.extension or "").lower()
    if ext != "zip":
        raise AppException("Only .zip is supported", status_code=400)
    disk = _resolve_disk_path(src.storage_path)
    if not disk:
        raise AppException("Zip content missing on disk", status_code=404)

    dest_parent = target_folder_id if target_folder_id and target_folder_id > 0 else src.folder_id
    # create container folder named after zip
    base_name = f"{src.name}"
    folder_name = await next_available_folder_name(
        db, owner_id=owner_id, parent_id=dest_parent, requested_name=base_name
    )
    container = Folder(name=folder_name, parent_id=dest_parent, owner_id=owner_id, deleted=False)
    db.add(container)
    await db.flush()

    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    extract_root = (upload_dir / "extracted" / str(owner_id) / f"{container.id}").resolve()
    extract_root.mkdir(parents=True, exist_ok=True)

    created_files = 0
    with zfmod.ZipFile(disk, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not name or name.endswith("/"):
                # ensure folder path exists in DB tree lazily via file parents
                continue
            # path traversal guard
            target_path = (extract_root / name).resolve()
            if not str(target_path).startswith(str(extract_root)):
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src_f, open(target_path, "wb") as out_f:
                out_f.write(src_f.read())

            # map relative path to folder tree under container
            parts = Path(name).parts
            parent_id = container.id
            for folder_part in parts[:-1]:
                existing = await db.execute(
                    select(Folder).where(
                        Folder.name == folder_part,
                        Folder.parent_id == parent_id,
                        Folder.owner_id == owner_id,
                        Folder.deleted.is_(False),
                    )
                )
                folder = existing.scalar_one_or_none()
                if not folder:
                    folder = Folder(name=folder_part, parent_id=parent_id, owner_id=owner_id, deleted=False)
                    db.add(folder)
                    await db.flush()
                parent_id = folder.id

            filename = parts[-1]
            stem, dot, extension = filename.rpartition(".")
            if not dot:
                stem, extension = filename, ""
            rel_storage = str(target_path.relative_to(upload_dir))
            row = File(
                name=stem or filename,
                extension=extension.lower(),
                size=target_path.stat().st_size,
                folder_id=parent_id,
                owner_id=owner_id,
                storage_path=rel_storage,
                mime_type="",
                deleted=False,
            )
            db.add(row)
            created_files += 1

    await db.commit()
    return {
        "folder_id": container.id,
        "folder_name": container.name,
        "file_count": created_files,
    }
