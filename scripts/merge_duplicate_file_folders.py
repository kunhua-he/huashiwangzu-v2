#!/usr/bin/env python3
"""Merge active duplicate framework folders under the same owner and parent.

Dry-run by default. With --apply, the lowest id folder is kept as canonical;
files and child folders from duplicate folders are moved into it. Name conflicts
are preserved with an auto suffix such as name(1).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.database import AsyncSessionLocal
from app.models.file import File, Folder
from app.services.file_service import _lock_folder_namespace, next_available_folder_name
from sqlalchemy import select, text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-id", type=int, default=0, help="0 means all owners")
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write-plan", default="", help="optional JSON plan path")
    return parser


async def _file_name_exists(
    db,
    *,
    owner_id: int,
    folder_id: int | None,
    name: str,
    extension: str,
    exclude_id: int | None = None,
) -> bool:
    stmt = select(File.id).where(
        File.owner_id == owner_id,
        File.folder_id == folder_id,
        File.name == name,
        File.extension == extension,
        File.deleted.is_(False),
    )
    if exclude_id is not None:
        stmt = stmt.where(File.id != exclude_id)
    return (await db.execute(stmt.limit(1))).scalar_one_or_none() is not None


async def _next_available_file_name(
    db,
    *,
    owner_id: int,
    folder_id: int | None,
    requested_name: str,
    extension: str,
    exclude_id: int | None = None,
) -> str:
    base = requested_name.strip()
    if not base:
        base = "untitled"
    if not await _file_name_exists(
        db,
        owner_id=owner_id,
        folder_id=folder_id,
        name=base,
        extension=extension,
        exclude_id=exclude_id,
    ):
        return base
    index = 1
    while True:
        candidate = f"{base}({index})"
        if not await _file_name_exists(
            db,
            owner_id=owner_id,
            folder_id=folder_id,
            name=candidate,
            extension=extension,
            exclude_id=exclude_id,
        ):
            return candidate
        index += 1


async def _duplicate_groups(db, owner_id: int, limit: int) -> list[dict]:
    owner_filter = "AND owner_id = :owner_id" if owner_id else ""
    limit_sql = "LIMIT :limit" if limit else ""
    result = await db.execute(
        text(
            f"""
            SELECT owner_id, parent_id, name, array_agg(id ORDER BY id) AS ids, count(*) AS count
            FROM framework_file_folders
            WHERE deleted = false
              {owner_filter}
            GROUP BY owner_id, parent_id, name
            HAVING count(*) > 1
            ORDER BY owner_id, parent_id NULLS FIRST, name
            {limit_sql}
            """
        ),
        {"owner_id": owner_id, "limit": limit},
    )
    return [dict(row._mapping) for row in result]


async def _merge_group(db, group: dict, *, apply: bool) -> list[dict]:
    owner_id = int(group["owner_id"])
    parent_id = int(group["parent_id"]) if group["parent_id"] is not None else None
    ids = [int(item) for item in group["ids"]]
    canonical_id = ids[0]
    duplicate_ids = ids[1:]
    actions: list[dict] = []

    await _lock_folder_namespace(db, owner_id, parent_id)
    canonical = await db.get(Folder, canonical_id)
    if not canonical or canonical.deleted:
        return actions

    for duplicate_id in duplicate_ids:
        duplicate = await db.get(Folder, duplicate_id)
        if not duplicate or duplicate.deleted:
            continue

        files = (
            await db.execute(
                select(File)
                .where(File.folder_id == duplicate_id, File.owner_id == owner_id, File.deleted.is_(False))
                .order_by(File.id.asc())
            )
        ).scalars().all()
        for file in files:
            final_name = await _next_available_file_name(
                db,
                owner_id=owner_id,
                folder_id=canonical_id,
                requested_name=file.name,
                extension=file.extension or "",
                exclude_id=int(file.id),
            )
            actions.append({
                "action": "move_file",
                "file_id": int(file.id),
                "from_folder_id": duplicate_id,
                "to_folder_id": canonical_id,
                "old_name": file.name,
                "new_name": final_name,
                "extension": file.extension,
            })
            if apply:
                file.folder_id = canonical_id
                file.name = final_name

        child_folders = (
            await db.execute(
                select(Folder)
                .where(Folder.parent_id == duplicate_id, Folder.owner_id == owner_id, Folder.deleted.is_(False))
                .order_by(Folder.id.asc())
            )
        ).scalars().all()
        for child in child_folders:
            final_name = await next_available_folder_name(
                db,
                owner_id=owner_id,
                parent_id=canonical_id,
                requested_name=child.name,
                exclude_id=int(child.id),
            )
            actions.append({
                "action": "move_folder",
                "folder_id": int(child.id),
                "from_parent_id": duplicate_id,
                "to_parent_id": canonical_id,
                "old_name": child.name,
                "new_name": final_name,
            })
            if apply:
                child.parent_id = canonical_id
                child.name = final_name

        actions.append({
            "action": "soft_delete_duplicate_folder",
            "folder_id": duplicate_id,
            "canonical_folder_id": canonical_id,
            "name": duplicate.name,
        })
        if apply:
            duplicate.deleted = True
            duplicate.deleted_at = datetime.now(timezone.utc)

    return actions


async def _run(args: argparse.Namespace) -> dict:
    owner_id = max(0, int(args.owner_id or 0))
    limit = max(0, int(args.limit or 0))
    async with AsyncSessionLocal() as db:
        groups = await _duplicate_groups(db, owner_id, limit)
        plan: list[dict] = []
        for group in groups:
            actions = await _merge_group(db, group, apply=bool(args.apply))
            plan.append({
                "owner_id": int(group["owner_id"]),
                "parent_id": int(group["parent_id"]) if group["parent_id"] is not None else None,
                "name": group["name"],
                "folder_ids": [int(item) for item in group["ids"]],
                "actions": actions,
            })
        if args.apply:
            await db.commit()
        else:
            await db.rollback()

    result = {
        "dry_run": not args.apply,
        "owner_id": owner_id or None,
        "duplicate_groups": len(groups),
        "planned_actions": sum(len(item["actions"]) for item in plan),
        "groups": plan[:50],
    }
    if args.write_plan:
        plan_path = Path(args.write_plan).expanduser()
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        result["plan_path"] = str(plan_path)
        result["plan_groups"] = len(plan)
    return result


def main() -> int:
    args = _build_parser().parse_args()
    print(json.dumps(asyncio.run(_run(args)), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
