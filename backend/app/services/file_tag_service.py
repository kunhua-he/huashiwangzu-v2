from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, NotFound
from app.models.file import File, Folder
from app.models.file_item_tag import FileItemTag

ALLOWED_TAGS = frozenset({"red", "orange", "yellow", "green", "blue", "purple", "gray"})
ALLOWED_ITEM_TYPES = frozenset({"file", "folder"})


def _normalize_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        tag = str(raw or "").strip().lower()
        if not tag or tag not in ALLOWED_TAGS or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


async def _assert_item_owned(
    db: AsyncSession,
    *,
    owner_id: int,
    item_type: str,
    item_id: int,
) -> None:
    if item_type not in ALLOWED_ITEM_TYPES:
        raise AppException("item_type must be file or folder", status_code=400)
    if item_id <= 0:
        raise AppException("item_id invalid", status_code=400)

    if item_type == "file":
        row = await db.get(File, item_id)
        if not row or row.deleted or int(row.owner_id) != int(owner_id):
            raise NotFound("File not found")
        return

    row = await db.get(Folder, item_id)
    if not row or row.deleted or int(row.owner_id) != int(owner_id):
        raise NotFound("Folder not found")


async def list_tags_map(db: AsyncSession, owner_id: int) -> dict[str, list[str]]:
    result = await db.execute(
        select(FileItemTag).where(FileItemTag.owner_id == owner_id).order_by(FileItemTag.item_type, FileItemTag.item_id, FileItemTag.tag)
    )
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in result.scalars().all():
        key = f"{row.item_type}:{int(row.item_id)}"
        if row.tag not in grouped[key]:
            grouped[key].append(row.tag)
    return dict(grouped)


async def get_item_tags(
    db: AsyncSession,
    *,
    owner_id: int,
    item_type: str,
    item_id: int,
) -> list[str]:
    await _assert_item_owned(db, owner_id=owner_id, item_type=item_type, item_id=item_id)
    result = await db.execute(
        select(FileItemTag.tag).where(
            FileItemTag.owner_id == owner_id,
            FileItemTag.item_type == item_type,
            FileItemTag.item_id == item_id,
        ).order_by(FileItemTag.tag)
    )
    return [str(tag) for tag in result.scalars().all()]


async def set_item_tags(
    db: AsyncSession,
    *,
    owner_id: int,
    item_type: str,
    item_id: int,
    tags: list[str] | None,
) -> list[str]:
    await _assert_item_owned(db, owner_id=owner_id, item_type=item_type, item_id=item_id)
    normalized = _normalize_tags(tags)

    await db.execute(
        delete(FileItemTag).where(
            FileItemTag.owner_id == owner_id,
            FileItemTag.item_type == item_type,
            FileItemTag.item_id == item_id,
        )
    )
    for tag in normalized:
        db.add(
            FileItemTag(
                owner_id=owner_id,
                item_type=item_type,
                item_id=item_id,
                tag=tag,
            )
        )
    await db.commit()
    return normalized


async def toggle_item_tag(
    db: AsyncSession,
    *,
    owner_id: int,
    item_type: str,
    item_id: int,
    tag: str,
) -> list[str]:
    tag_key = str(tag or "").strip().lower()
    if tag_key not in ALLOWED_TAGS:
        raise AppException("unsupported tag", status_code=400)
    current = await get_item_tags(db, owner_id=owner_id, item_type=item_type, item_id=item_id)
    if tag_key in current:
        next_tags = [t for t in current if t != tag_key]
    else:
        next_tags = [*current, tag_key]
    return await set_item_tags(
        db,
        owner_id=owner_id,
        item_type=item_type,
        item_id=item_id,
        tags=next_tags,
    )
